DEVKITPRO ?= /opt/devkitpro
DEVKITA64 ?= $(DEVKITPRO)/devkitA64
CXX := $(DEVKITA64)/bin/aarch64-none-elf-g++
export PATH := $(DEVKITPRO)/tools/bin:$(PATH)
TARGET := nx-ukrainian-news
CXXFLAGS := -O2 -g0 -Wall -Wextra -Werror -std=gnu++17 -march=armv8-a+crc+crypto -mtune=cortex-a57 -mtp=soft -fPIE -ffunction-sections -isystem $(DEVKITPRO)/libnx/include -D__SWITCH__
LDFLAGS := -specs=$(DEVKITPRO)/libnx/switch.specs -g0 -march=armv8-a+crc+crypto -mtp=soft -Wl,--gc-sections -L$(DEVKITPRO)/libnx/lib

all: $(TARGET).nro
$(TARGET).elf: main.cpp msgpack.hpp verified_store.hpp
	$(CXX) $(CXXFLAGS) main.cpp $(LDFLAGS) -lnx -o $@
$(TARGET).nacp: Makefile
	nacptool --create "Ukrainian News Refresh 0.1.7" "andotsy" "0.1.7" $@
$(TARGET).nro: $(TARGET).elf $(TARGET).nacp
	elf2nro $(TARGET).elf $@ --nacp=$(TARGET).nacp

.PHONY: all
