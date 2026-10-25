// SPDX-License-Identifier: MIT
#pragma once
#include <exception>
#include <stdexcept>

namespace newsmsg {
// Store supplies read(), write(bytes), and commit(). Never accept an unexpected
// live original. A partial write, failed commit, or wrong readback restores and
// verifies the exact original before propagating the failure.
template<class Store, class Bytes>
void replaceVerified(Store& store,const Bytes& original,const Bytes& replacement) {
    Bytes current=store.read();
    if (current==replacement) return;
    if (current!=original) throw std::runtime_error("Stored article changed since backup");
    try {
        store.write(replacement);
        store.commit();
        if (store.read()!=replacement) throw std::runtime_error("Stored article readback mismatch");
    } catch (...) {
        auto failure=std::current_exception();
        try {
            store.write(original);
            store.commit();
            if (store.read()!=original) throw std::runtime_error("Restore readback mismatch");
        } catch (...) {
            throw std::runtime_error("Stored article restore failed; keep the verified SD backup");
        }
        std::rethrow_exception(failure);
    }
}
}
