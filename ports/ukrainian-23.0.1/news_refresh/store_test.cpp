// SPDX-License-Identifier: MIT
#include <cassert>
#include <iostream>
#include <string>
#include "verified_store.hpp"

struct Store {
    std::string bytes="original";
    unsigned writes=0,commits=0,reads=0;
    bool partial=false,commitFailure=false,wrongReadback=false,restoreFailure=false,readFailure=false;
    std::string read() {
        ++reads;
        if(readFailure) throw std::runtime_error("read failed");
        if(wrongReadback && reads==2) return "wrong";
        return bytes;
    }
    void write(const std::string& value) {
        ++writes;
        if((partial && writes==1) || (restoreFailure && writes==2)) {
            bytes="partial";throw std::runtime_error("write failed");
        }
        bytes=value;
    }
    void commit() {
        ++commits;
        if(commitFailure && commits==1) throw std::runtime_error("commit failed");
    }
};
static std::string attempt(Store& store) {
    try { newsmsg::replaceVerified(store,std::string("original"),std::string("translated")); }
    catch(const std::exception& e) { return e.what(); }
    return {};
}
int main() {
    { struct IntegerStore {
        int value=0,writes=0;
        int read() { return value; }
        void write(int next) { value=next;++writes; }
        void commit() {}
      } s;
      newsmsg::replaceVerified(s,0,1);assert(s.value==1 && s.writes==1);
      newsmsg::replaceVerified(s,0,1);assert(s.value==1 && s.writes==1);
      newsmsg::replaceVerified(s,1,0);assert(s.value==0 && s.writes==2); }
    { Store s;assert(attempt(s).empty());assert(s.bytes=="translated" && s.writes==1 && s.commits==1);
      assert(attempt(s).empty());assert(s.writes==1 && s.commits==1); }
    { Store s;s.bytes="changed";assert(!attempt(s).empty());assert(s.bytes=="changed" && !s.writes && !s.commits); }
    { Store s;s.partial=true;assert(attempt(s)=="write failed");assert(s.bytes=="original" && s.writes==2 && s.commits==1); }
    { Store s;s.commitFailure=true;assert(attempt(s)=="commit failed");assert(s.bytes=="original" && s.commits==2); }
    { Store s;s.wrongReadback=true;assert(attempt(s)=="Stored article readback mismatch");assert(s.bytes=="original" && s.writes==2 && s.commits==2); }
    { Store s;s.partial=true;s.restoreFailure=true;assert(attempt(s).find("restore failed")!=std::string::npos);assert(s.bytes=="partial"); }
    { struct RejectedStore {
        int read() { return 1; }
        void write(int value) { throw std::runtime_error(value ? "restore: 0x1927D" : "hide: 0x1927D"); }
        void commit() {}
      } s;
      try { newsmsg::replaceVerified(s,1,0);assert(false); }
      catch(const std::exception& e) {
        std::string message=e.what();
        assert(message.find("restore: 0x1927D")!=std::string::npos);
        assert(message.find("original error: hide: 0x1927D")!=std::string::npos);
      } }
    { Store s;s.readFailure=true;assert(attempt(s)=="read failed");assert(s.bytes=="original" && !s.writes); }
    std::cout<<"Verified store: success, idempotence, stale input, partial write, commit failure, bad readback, failed restore and read failure checked\n";
}
