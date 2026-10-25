// SPDX-License-Identifier: MIT
#pragma once
#include <cstdint>
#include <cstring>
#include <map>
#include <stdexcept>
#include <string>
#include <vector>

namespace newsmsg {
using Bytes = std::vector<uint8_t>;
struct Node {
    size_t start{}, payload{}, end{};
    uint8_t tag{};
    bool string{}, map{}, array{};
    std::vector<Node> children;
};
class Parser {
    const Bytes& in;
    size_t p{}, nodes{};
    void require(size_t n) { if (n > in.size() - p) throw std::runtime_error("Truncated MessagePack"); }
    uint64_t integer(unsigned n) {
        require(n); uint64_t v=0;
        for (unsigned i=0;i<n;++i) v=(v<<8)|in[p++];
        return v;
    }
public:
    explicit Parser(const Bytes& b): in(b) {}
    Node parse(unsigned depth=0) {
        if (depth>32 || ++nodes>200000) throw std::runtime_error("MessagePack limit");
        require(1); Node n; n.start=p; n.tag=in[p++]; uint64_t count=0, width=0;
        auto t=n.tag;
        if ((t&0xe0)==0xa0) { n.string=true; width=t&31; }
        else if ((t&0xf0)==0x80) { n.map=true; count=t&15; }
        else if ((t&0xf0)==0x90) { n.array=true; count=t&15; }
        else if (t<=0x7f || t>=0xe0 || t==0xc0 || t==0xc2 || t==0xc3) {}
        else if (t==0xd9 || t==0xda || t==0xdb) { n.string=true; width=integer(1u<<(t-0xd9)); }
        else if (t==0xc4 || t==0xc5 || t==0xc6) width=integer(1u<<(t-0xc4));
        else if (t==0xc7 || t==0xc8 || t==0xc9) width=integer(1u<<(t-0xc7))+1;
        else if (t==0xca) width=4;
        else if (t==0xcb) width=8;
        else if (t>=0xcc && t<=0xcf) width=1u<<(t-0xcc);
        else if (t>=0xd0 && t<=0xd3) width=1u<<(t-0xd0);
        else if (t>=0xd4 && t<=0xd8) width=(1u<<(t-0xd4))+1;
        else if (t==0xdc || t==0xdd) { n.array=true; count=integer(t==0xdc?2:4); }
        else if (t==0xde || t==0xdf) { n.map=true; count=integer(t==0xde?2:4); }
        else throw std::runtime_error("Unsupported MessagePack tag");
        n.payload=p;
        if (n.map || n.array) {
            if (count>100000 || count*(n.map?2:1)>in.size()-p) throw std::runtime_error("Container limit");
            for (uint64_t i=0;i<count*(n.map?2:1);++i) n.children.push_back(parse(depth+1));
        } else { require(width); p+=width; }
        n.end=p; return n;
    }
    Node document() { Node n=parse(); if (p!=in.size()) throw std::runtime_error("Trailing data"); return n; }
};
inline std::string str(const Node& n,const Bytes& in) {
    if (!n.string) throw std::runtime_error("Expected string");
    return std::string(reinterpret_cast<const char*>(in.data()+n.payload),n.end-n.payload);
}
inline const Node* member(const Node& n,const Bytes& in,const std::string& name) {
    if (!n.map) return nullptr;
    for (size_t i=0;i<n.children.size();i+=2)
        if (n.children[i].string && str(n.children[i],in)==name) return &n.children[i+1];
    return nullptr;
}
inline const Node* field(const Node& n,const Bytes& in,const std::string& path) {
    auto pos=path.find('.'); auto child=member(n,in,path.substr(0,pos));
    return child && pos!=std::string::npos ? field(*child,in,path.substr(pos+1)) : child;
}
// The News data service returns an allocated storage buffer. On the tested
// console the MessagePack map occupies only part of a 512 KiB buffer. Accept
// zero-filled storage padding, while retaining strict parsing everywhere else.
inline Node articleRoot(const Bytes& in) {
    Node root=Parser(in).parse();
    if (!root.map) throw std::runtime_error("News article root is not a map");
    for (size_t i=root.end;i<in.size();++i)
        if (in[i]) throw std::runtime_error("Nonzero trailing News data");
    return root;
}
inline Bytes articleBytes(const Bytes& in) {
    Node root=articleRoot(in);
    return Bytes(in.begin(),in.begin()+root.end);
}
struct Translation { std::string target; bool subject{}; };
using Table=std::map<std::string,Translation>;
inline Table parseTable(const Bytes& b) {
    if (b.size()<12 || std::memcmp(b.data(),"NXUKNEWS",8)) throw std::runtime_error("Invalid translation table");
    size_t p=8;
    auto integer=[&] () -> uint32_t {
        if(p+4>b.size()) throw std::runtime_error("Truncated translation table");
        uint32_t v=b[p]|uint32_t(b[p+1])<<8|uint32_t(b[p+2])<<16|uint32_t(b[p+3])<<24;p+=4;return v;
    };
    auto count=integer();if(count!=41) throw std::runtime_error("Unexpected translation count");
    Table table;
    for(uint32_t i=0;i<count;++i) {
        auto flags=integer(),a=integer(),c=integer();
        if(flags>1 || a>65536 || c>65536 || p+a+c>b.size()) throw std::runtime_error("Invalid translation length");
        std::string source(reinterpret_cast<const char*>(b.data()+p),a);p+=a;
        std::string target(reinterpret_cast<const char*>(b.data()+p),c);p+=c;
        if(table.count(source)) throw std::runtime_error("Ambiguous translation");
        table.emplace(source,Translation{target,bool(flags&1)});
    }
    if(p!=b.size()) throw std::runtime_error("Trailing table data");
    return table;
}
inline void putString(Bytes& out,const std::string& value) {
    size_t n=value.size();
    if (n<32) out.push_back(0xa0|n);
    else {
        unsigned width=n<=255?1:n<=65535?2:4;
        out.push_back(width==1?0xd9:width==2?0xda:0xdb);
        for (int shift=(width-1)*8;shift>=0;shift-=8) out.push_back((n>>shift)&255);
    }
    out.insert(out.end(),value.begin(),value.end());
}
inline bool allowed(const std::string& path) {
    return path=="topic_name" || path=="subject.text" || path=="body.text" ||
           path=="footer.text" || path=="more.system_applet.text" || path=="more.text";
}
inline void rewrite(const Node& n,const Bytes& in,Bytes& out,const Table& table,
                    const std::string& path,unsigned& changes) {
    if (n.string && allowed(path)) {
        auto found=table.find(str(n,in));
        if (found!=table.end()) { putString(out,found->second.target); ++changes; return; }
    }
    if (n.map || n.array) {
        out.insert(out.end(),in.begin()+n.start,in.begin()+n.payload);
        for (size_t i=0;i<n.children.size();++i) {
            auto& child=n.children[i];
            if (n.map && i%2==0) out.insert(out.end(),in.begin()+child.start,in.begin()+child.end);
            else {
                std::string next=path;
                if (n.map && n.children[i-1].string) next+=(path.empty()?"":".")+str(n.children[i-1],in);
                else next+="[]";
                rewrite(child,in,out,table,next,changes);
            }
        }
    } else out.insert(out.end(),in.begin()+n.start,in.begin()+n.end);
}
struct RewriteResult { Bytes data; unsigned changes{}; bool tutorial{}; };
inline RewriteResult translate(const Bytes& in,const Table& table) {
    Node root=articleRoot(in);
    auto language=field(root,in,"language"), topic=field(root,in,"topic_id"), subject=field(root,in,"subject.text");
    RewriteResult result;
    if (!language || !topic || !subject || !language->string || !topic->string || !subject->string) return result;
    if (str(*language,in)!="ru" || str(*topic,in)!="nx_notice") return result;
    auto title=str(*subject,in); bool known=false;
    for (const auto& entry:table) if (entry.second.subject && (entry.first==title || entry.second.target==title)) known=true;
    if (!known) return result;
    result.tutorial=true;
    rewrite(root,in,result.data,table,"",result.changes);
    Node after=Parser(result.data).document();
    for (const std::string key:{"news_id","language","topic_id","published_at","supported_languages","user_id"}) {
        auto a=field(root,in,key), b=field(after,result.data,key);
        if (bool(a)!=bool(b) || (a && Bytes(in.begin()+a->start,in.begin()+a->end)!=
                                      Bytes(result.data.begin()+b->start,result.data.begin()+b->end)))
            throw std::runtime_error("Article identity changed");
    }
    return result;
}
}
