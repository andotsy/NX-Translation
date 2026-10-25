// SPDX-License-Identifier: MIT
#include <fstream>
#include <iostream>
#include "msgpack.hpp"
using namespace newsmsg;
static Bytes read(const char* path) {
    std::ifstream f(path,std::ios::binary);
    if(!f) throw std::runtime_error("Cannot read test input");
    return Bytes(std::istreambuf_iterator<char>(f),{});
}
int main(int argc,char** argv) {
    try {
        if(argc!=4 && argc!=5) return 1;
        Table table=parseTable(read(argv[1]));Bytes original=read(argv[2]);
        bool native=argc==5 && std::string(argv[4])=="--native-buffer";
        if(argc==5 && !native) return 1;
        Bytes payload=native?nativeArticleBytes(original):original;
        auto result=translate(payload,table);
        auto output=result.tutorial?result.data:original;
        std::ofstream f(argv[3],std::ios::binary);
        f.write(reinterpret_cast<const char*>(output.data()),output.size());
        if(!f) return 3;
        std::cout<<"{\"tutorial\":"<<(result.tutorial?"true":"false")<<",\"changes\":"<<result.changes
                 <<",\"payload_bytes\":"<<payload.size()<<"}\n";
        return 0;
    } catch(const std::exception& error) {std::cerr<<error.what()<<"\n";return 2;}
}
