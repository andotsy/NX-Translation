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
    return parseTable(load(BASE+"/translations.bin",1024*1024));
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
struct Article { NewsRecord record; Bytes original,originalPayload,translated; unsigned changes; std::string backup; };
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
        printLog("Ukrainian News tutorials - 23.0.1 (helper 0.1.5)\n");
        if (hosversionGet()!=MAKEHOSVERSION(23,0,1)) throw std::runtime_error("This build is for firmware 23.0.1 only");
        printLog("Reads existing built-in Russian tutorials. No network or keys.");
        printLog("Original articles are backed up before any change.");
        Table table=loadTable();
        check(newsInitialize(NewsServiceType_Administrator),"Initialize News service");initialized=true;
        check(newsCreateNewsDatabaseService(&database),"Open News index");
        std::vector<Article> articles;unsigned scanned=0,already=0,skipped=0;size_t retained=0;
        bool exhausted=false;
        for (unsigned page=0;page<64;++page) {
            NewsRecord records[64]{};uint32_t count=0;
            check(newsDatabaseGetList(&database,records,64,"","",&count,page*64),"List News index");
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
                articles.push_back(Article{records[i],std::move(original),std::move(payload),std::move(result.data),result.changes,{}});
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
            std::snprintf(summary,sizeof(summary),"Ready to replace %u matching text fields. IDs/images/metadata stay unchanged.",total);printLog(summary);
            printLog("\nA: apply Ukrainian text\nB / +: exit without changes");
            consoleUpdate(nullptr);
            bool apply=false;
            while(appletMainLoop()) {
                padUpdate(&pad);auto keys=padGetButtonsDown(&pad);
                if (keys&(HidNpadButton_B|HidNpadButton_Plus)) break;
                if (keys&HidNpadButton_A) {apply=true;break;}
                consoleUpdate(nullptr);
            }
            if (apply) {
                unsigned posted=0,attempted=0;
                try {
                    for(auto& article:articles) {
                        if (load(article.backup)!=article.original) throw std::runtime_error("Backup changed; stopping");
                        if (nativeArticleBytes(readArticle(article.record))!=article.originalPayload)
                            throw std::runtime_error("News changed since backup; stopping");
                        ++attempted;
                        check(newsPostLocalNews(article.translated.data(),article.translated.size()),"Update tutorial");
                        ++posted;
                        Bytes actual=readArticle(article.record);
                        if (nativeArticleBytes(actual)!=article.translated) throw std::runtime_error("Article readback mismatch");
                    }
                    std::snprintf(summary,sizeof(summary),"SUCCESS: %u tutorial articles updated and read back.",posted);printLog(summary);
                    printLog("Exit, reopen News and check the article titles and bodies.");
                    printLog("Keep the backup folder until the result is confirmed.");
                } catch (const std::exception& error) {
                    printLog(error.what());printLog("Restoring backed-up originals for any attempted updates...");
                    unsigned restored=0;
                    for (size_t i=0;i<attempted;++i) {
                        auto& article=articles[i];
                        try {
                            Bytes original=nativeArticleBytes(load(article.backup));
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
