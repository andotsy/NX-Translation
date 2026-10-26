// SPDX-License-Identifier: MIT
#include <switch.h>
#include <cerrno>
#include <cstdio>
#include <cstdlib>
#include <ctime>
#include <fstream>
#include <fcntl.h>
#include <sys/stat.h>
#include <unistd.h>
#include "msgpack.hpp"
#include "verified_store.hpp"

using namespace newsmsg;
static const std::string BASE="sdmc:/switch/nx-ukrainian-news";
static FILE* logFile=nullptr;
static void check(Result rc,const char* operation) {
    if (R_FAILED(rc)) {
        char buffer[128]; std::snprintf(buffer,sizeof(buffer),"%s: 0x%08X",operation,rc);
        throw std::runtime_error(buffer);
    }
}
static Bytes load(const std::string& path,size_t limit=16*1024*1024) {
    std::ifstream f(path,std::ios::binary|std::ios::ate);
    if (!f) throw std::runtime_error("Cannot open local file");
    auto size=f.tellg(); if (size<0 || size_t(size)>limit) throw std::runtime_error("Local file size limit");
    Bytes data(size); f.seekg(0);
    if (size && !f.read(reinterpret_cast<char*>(data.data()),size)) throw std::runtime_error("Local read failed");
    return data;
}
static void saveNew(const std::string& path,const Bytes& data) {
    int fd=open(path.c_str(),O_WRONLY|O_CREAT|O_EXCL,0666);
    if(fd<0) throw std::runtime_error("Backup already exists or cannot be created");
    FILE* f=fdopen(fd,"wb");
    if(!f) {close(fd);throw std::runtime_error("Cannot open backup stream");}
    if (!f) throw std::runtime_error("Backup already exists or cannot be created");
    bool good=std::fwrite(data.data(),1,data.size(),f)==data.size();
    good=(std::fflush(f)==0)&&good; good=(fsync(fileno(f))==0)&&good;
    good=(std::fclose(f)==0)&&good;
    if (!good || load(path)!=data) throw std::runtime_error("Backup verification failed; nothing posted");
}
static Table loadTable() {
    return parseTable(load(BASE+"/translations-0.1.6.bin",1024*1024));
}
struct ArticleReader {
    NewsDataService service{};
    ~ArticleReader() { if (service.s.session) newsDataClose(&service); }
};
static Bytes readArticle(NewsRecord& record) {
    // Readers hold the service's shared lock until their sessions close. Give
    // each read its own scope so a later post can acquire the exclusive lock.
    ArticleReader reader;
    check(newsCreateNewsDataService(&reader.service),"Create News article reader");
    check(newsDataOpenWithNewsRecord(&reader.service,&record),"Open News article");
    uint64_t size=0;check(newsDataGetSize(&reader.service,&size),"Read News size");
    if (!size || size>8*1024*1024) throw std::runtime_error("News article size limit");
    Bytes bytes(size);uint64_t pos=0;
    while (pos<size) {
        uint64_t read=0;
        check(newsDataRead(&reader.service,&read,pos,bytes.data()+pos,size-pos),"Read News article");
        if (!read || read>size-pos) throw std::runtime_error("Short News article read");
        pos+=read;
    }
    return bytes;
}
struct Article { NewsRecord record; Bytes original,originalPayload,translated; unsigned changes; std::string backup; bool retired=false; NewsRecord replacementRecord{}; };
struct NewsPause {
    Service service{};
    NewsPause() {
        check(serviceDispatch(newsGetServiceSession(),50100,
              .out_num_objects=1,.out_objects=&service),"Suspend background News tasks");
    }
    ~NewsPause() { if(service.session) serviceClose(&service); }
};
struct NewsIndex {
    NewsDatabaseService service{};
    NewsIndex() { check(newsCreateNewsDatabaseService(&service),"Open News index"); }
    ~NewsIndex() { if(service.s.session) newsDatabaseClose(&service); }
};
static std::string recordFilter(const NewsRecord& record) {
    size_t n=strnlen(record.news_id,sizeof(record.news_id));
    if(n!=22 || record.user_id[0] || std::memcmp(record.topic_id.name,"nx_notice",10))
        throw std::runtime_error("Unexpected tutorial record identity");
    std::string name(record.news_id,n);
    for(char c:name) if(!((c>='A' && c<='Z') || (c>='0' && c<='9')))
        throw std::runtime_error("Unexpected tutorial record ID");
    return "news_id='"+name+"' AND user_id='' AND topic_id='nx_notice'";
}
struct VisibilityStore {
    NewsDatabaseService& database;
    std::string filter;
    uint32_t count(const std::string& condition) {
        uint32_t result=0;
        check(newsDatabaseCount(&database,condition.c_str(),&result),"Check News index state");
        return result;
    }
    int32_t read() {
        if(count(filter)!=1) throw std::runtime_error("Expected exactly one original News record");
        if(count(filter+" AND opted_in=0")==1) return 0;
        if(count(filter+" AND opted_in=1")==1) return 1;
        throw std::runtime_error("Unexpected original article visibility; nothing changed");
    }
    void write(int32_t value) {
        if(value!=0 && value!=1) throw std::runtime_error("Invalid article visibility");
        // Firmware 23.0.1 restricts this command to an explicit column allowlist.
        // opted_in is writable; expire_at is rejected before executing SQL.
        static const char column[]="opted_in";
        Result rc=serviceDispatchIn(&database.s,3,value,
            .buffer_attrs={SfBufferAttr_HipcPointer|SfBufferAttr_In,SfBufferAttr_HipcPointer|SfBufferAttr_In},
            .buffers={{column,sizeof(column)},{filter.c_str(),filter.size()+1}});
        if(logFile) {
            std::fprintf(logFile,"Set original opted_in=%d: 0x%08X\n",value,rc);
            std::fflush(logFile);
        }
        check(rc,"Set original article visibility");
    }
    // This IPC command commits in the News service before returning.
    void commit() {}
};
static bool subscriptionArticle(const Article& article) {
    auto root=Parser(article.originalPayload).document();
    auto id=field(root,article.originalPayload,"news_id");
    if(!id) return false;
    uint64_t value=0;
    if(id->tag<=0x7f) value=id->tag;
    else if(id->tag>=0xcc && id->tag<=0xcf) {
        for(size_t i=id->payload;i<id->end;++i) value=(value<<8)|article.originalPayload[i];
    } else return false;
    return value==442;
}
static void retireSubscriptionArticle(Article& article) {
    std::string originalFilter=recordFilter(article.record);
    std::string originalId(article.record.news_id);
    if(originalId.substr(2)!="00000000000000000442" || originalId.substr(0,2)=="LS")
        throw std::runtime_error("Expected the original non-local subscription record");
    NewsIndex index;
    NewsRecord replacement{};unsigned matches=0;bool exhausted=false;
    // The posting service may allocate a different local ID. Discover the copy
    // by its complete transformed payload instead of guessing an LS record ID.
    for(unsigned page=0;page<64;++page) {
        NewsRecord records[64]{};uint32_t count=0;
        check(newsDatabaseGetList(&index.service,records,64,"","",&count,page*64),"Find existing Ukrainian copy");
        if(count>64) throw std::runtime_error("Invalid replacement index count");
        for(uint32_t i=0;i<count;++i) {
            if(records[i].user_id[0] ||
               strnlen(records[i].topic_id.name,sizeof(records[i].topic_id.name))!=9 ||
               std::memcmp(records[i].topic_id.name,"nx_notice",9)) continue;
            std::string candidateFilter=recordFilter(records[i]);
            if(candidateFilter==originalFilter) continue;
            Bytes candidate=readArticle(records[i]);
            Bytes payload=nativeArticleBytes(candidate);
            if(payload==article.translated) {
                ++matches;replacement=records[i];
                if(logFile) std::fprintf(logFile,"Verified Ukrainian copy record: %s\n",records[i].news_id);
            } else {
                auto expectedRoot=Parser(article.translated).document();
                auto actualRoot=Parser(payload).document();
                auto expectedTitle=field(expectedRoot,article.translated,"subject.text");
                auto actualTitle=field(actualRoot,payload,"subject.text");
                if(expectedTitle && actualTitle && expectedTitle->string && actualTitle->string &&
                   str(*expectedTitle,article.translated)==str(*actualTitle,payload)) {
                    saveNew(article.backup+".candidate-"+std::to_string(page*64+i),candidate);
                    if(logFile) std::fprintf(logFile,"Same-title copy differs: %s\n",records[i].news_id);
                }
            }
        }
        if(count<64) { exhausted=true;break; }
    }
    if(!exhausted) throw std::runtime_error("Replacement listing limit; nothing retired");
    if(matches!=1) {
        saveNew(article.backup+".expected",article.translated);
        throw std::runtime_error("No unique exact Ukrainian copy found; nothing retired");
    }
    if(nativeArticleBytes(readArticle(replacement))!=article.translated)
        throw std::runtime_error("Ukrainian copy changed; nothing retired");
    VisibilityStore store{index.service,originalFilter};
    if(store.read()!=1) throw std::runtime_error("Original article is already hidden; nothing changed");
    std::string metadata="original_record="+originalId+"\noriginal_opted_in=1\nreplacement_record="+std::string(replacement.news_id)+"\n";
    saveNew(article.backup+".index-backup",Bytes(metadata.begin(),metadata.end()));
    replaceVerified(store,int32_t(1),int32_t(0));
    article.retired=true;article.replacementRecord=replacement;
    if(store.count(originalFilter+" AND opted_in=1")!=0)
        throw std::runtime_error("Old Russian article is still eligible for the News list");
    if(nativeArticleBytes(readArticle(replacement))!=article.translated)
        throw std::runtime_error("Translated copy changed during retirement");
}
static void restoreRetiredArticle(Article& article) {
    NewsIndex index;VisibilityStore store{index.service,recordFilter(article.record)};
    replaceVerified(store,int32_t(0),int32_t(1));article.retired=false;
}
static void printLog(const char* text) {
    std::printf("%s\n",text);
    if (logFile) { std::fprintf(logFile,"%s\n",text);std::fflush(logFile); }
}
int main(int argc,char** argv) {
    (void)argc;(void)argv;
    consoleInit(nullptr);
    PadState pad;padConfigureInput(1,HidNpadStyleSet_NpadStandard);padInitializeDefault(&pad);
    bool initialized=false;NewsDatabaseService database{};
    try {
        mkdir(BASE.c_str(),0777);
        logFile=std::fopen((BASE+"/last-run.log").c_str(),"w");
        printLog("Ukrainian News articles - 23.0.1 (helper 0.1.10)\n");
        if (hosversionGet()!=MAKEHOSVERSION(23,0,1)) throw std::runtime_error("This build is for firmware 23.0.1 only");
        printLog("Reads existing built-in Russian tutorials. No network or keys.");
        printLog("Original articles are backed up before any change.");
        Table table=loadTable();
        check(newsInitialize(NewsServiceType_Administrator),"Initialize News service");initialized=true;
        check(newsCreateNewsDatabaseService(&database),"Open News index");
        std::vector<Article> articles;unsigned scanned=0,already=0,skipped=0;size_t retained=0;
        auto now=time(nullptr);
        if(now<2) throw std::runtime_error("Console clock must be set before checking article expiration");
        std::string activeFilter="opted_in=1 AND (expire_at=0 OR expire_at>="+std::to_string(static_cast<long long>(now))+")";
        bool exhausted=false;
        for (unsigned page=0;page<64;++page) {
            NewsRecord records[64]{};uint32_t count=0;
            check(newsDatabaseGetList(&database,records,64,activeFilter.c_str(),"",&count,page*64),"List News index");
            if (count>64) throw std::runtime_error("Invalid News count");
            scanned+=count;
            for (uint32_t i=0;i<count;++i) {
                if (strnlen(records[i].topic_id.name,sizeof(records[i].topic_id.name))!=9 ||
                    std::memcmp(records[i].topic_id.name,"nx_notice",9) || records[i].user_id[0]) continue;
                Bytes original=readArticle(records[i]);
                if (retained+original.size()>12*1024*1024) throw std::runtime_error("Tutorial memory limit; no updates made");
                Bytes payload=nativeArticleBytes(original);
                RewriteResult result=translate(payload,table);
                if (!result.tutorial) { ++skipped;continue; }
                if (!result.changes) { ++already;continue; }
                size_t needed=original.size()+payload.size()+result.data.size();
                if (retained+needed>12*1024*1024) throw std::runtime_error("Tutorial memory limit; no updates made");
                retained+=needed;
                articles.push_back(Article{records[i],std::move(original),std::move(payload),std::move(result.data),result.changes,{},false,{}});
            }
            if (count<64) { exhausted=true;break; }
        }
        if (!exhausted) throw std::runtime_error("News listing limit; no updates made");
        // The index also holds a shared lock, even between individual queries.
        // It is no longer needed after enumeration and must close before posts.
        newsDatabaseClose(&database);
        char summary[160];std::snprintf(summary,sizeof(summary),"Scanned %u records; %zu tutorials need translation; %u already translated.",scanned,articles.size(),already);printLog(summary);
        std::snprintf(summary,sizeof(summary),"Other built-in records skipped: %u. Other channels unchanged.",skipped);printLog(summary);
        if (!articles.empty()) {
            if (articles.size()>64) throw std::runtime_error("Unexpected tutorial count");
            std::string directory;
            for (unsigned i=0;i<1000;++i) {
                directory=BASE+"/backup-"+std::to_string(static_cast<long long>(time(nullptr)))+"-"+std::to_string(i);
                if (mkdir(directory.c_str(),0777)==0) break;
                if (errno!=EEXIST || i==999) throw std::runtime_error("Cannot create backup directory");
            }
            unsigned total=0;
            for (size_t i=0;i<articles.size();++i) {
                auto& article=articles[i];article.backup=directory+"/article-"+std::to_string(i)+".msgpack";
                saveNew(article.backup,article.original);total+=article.changes;
            }
            printLog("All original tutorial backups saved and verified.");
            if (logFile) { std::fprintf(logFile,"Backup directory: %s\n",directory.c_str());std::fflush(logFile); }
            std::snprintf(summary,sizeof(summary),"Ready: remove the Russian duplicate after verifying its Ukrainian copy (%u text fields).",total);printLog(summary);
            printLog("\nA: remove Russian duplicate / apply remaining translations\nB / +: exit without changes");
            consoleUpdate(nullptr);
            bool apply=false;
            while(appletMainLoop()) {
                padUpdate(&pad);auto keys=padGetButtonsDown(&pad);
                if (keys&(HidNpadButton_B|HidNpadButton_Plus)) break;
                if (keys&HidNpadButton_A) {apply=true;break;}
                consoleUpdate(nullptr);
            }
            if (apply) {
                // Keep cleanup suspended through both verification and rollback.
                NewsPause pause;
                unsigned posted=0,attempted=0;
                try {
                    for(auto& article:articles) {
                        if (load(article.backup)!=article.original) throw std::runtime_error("Backup changed; stopping");
                        if (nativeArticleBytes(readArticle(article.record))!=article.originalPayload)
                            throw std::runtime_error("News changed since backup; stopping");
                        ++attempted;
                        if(subscriptionArticle(article)) retireSubscriptionArticle(article);
                        else check(newsPostLocalNews(article.translated.data(),article.translated.size()),"Update tutorial");
                        ++posted;
                        Bytes actual=readArticle(article.retired?article.replacementRecord:article.record);
                        if (nativeArticleBytes(actual)!=article.translated) {
                            saveNew(article.backup+".expected",article.translated);
                            saveNew(article.backup+".readback",actual);
                            throw std::runtime_error("Article readback mismatch; exact comparison saved on SD");
                        }
                    }
                    std::snprintf(summary,sizeof(summary),"SUCCESS: %u Ukrainian articles verified; Russian duplicate hidden if present.",posted);printLog(summary);
                    printLog("Exit, reopen News and check the article titles and bodies.");
                    printLog("Keep the backup folder until the result is confirmed.");
                } catch (const std::exception& error) {
                    printLog(error.what());printLog("Restoring backed-up originals for any attempted updates...");
                    unsigned restored=0;
                    for (size_t i=0;i<attempted;++i) {
                        auto& article=articles[i];
                        try {
                            Bytes original=nativeArticleBytes(load(article.backup));
                            if(article.retired) restoreRetiredArticle(article);
                            bool unchanged=false;
                            try { unchanged=nativeArticleBytes(readArticle(article.record))==original; }
                            catch(const std::exception&) {}
                            if (!unchanged)
                                check(newsPostLocalNews(original.data(),original.size()),"Restore tutorial");
                            if (nativeArticleBytes(readArticle(article.record))==original) ++restored;
                        } catch(const std::exception&) {}
                    }
                    std::snprintf(summary,sizeof(summary),"Originals verified for %u of %u attempted articles. Keep backups and last-run.log.",restored,attempted);printLog(summary);
                }
            } else printLog("Exited without changing News articles.");
        } else printLog("No matching Russian tutorials need changes. Nothing written to News.");
    } catch (const std::exception& error) { printLog(error.what());printLog("Stopped. No unverified changes will be attempted."); }
    if (database.s.session) newsDatabaseClose(&database);
    if (initialized) newsExit();
    printLog("\nPress + to return to hbmenu.");
    while(appletMainLoop()) {
        padUpdate(&pad);if(padGetButtonsDown(&pad)&HidNpadButton_Plus) break;
        consoleUpdate(nullptr);
    }
    if (logFile) std::fclose(logFile);
    consoleExit(nullptr);return 0;
}
