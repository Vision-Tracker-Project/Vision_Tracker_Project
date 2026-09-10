# Cross toolchain. Linux uses tools from PATH. Override CROSS_COMPILE when the
# toolchain is elsewhere, for example:
# make CROSS_COMPILE='C:/arm-gnu-toolchain/bin/arm-none-eabi-'
CROSS_COMPILE ?= arm-none-eabi-
CC      := $(CROSS_COMPILE)gcc
OBJCOPY := $(CROSS_COMPILE)objcopy
OBJDUMP := $(CROSS_COMPILE)objdump
PROGRAMMER ?= STM32_Programmer_CLI
ST_FLASH   ?= st-flash
FLASH_ADDRESS ?= 0x08000000

OUT_FILE_NAME := rom_0x08000000
LDS_FILE_NAME := rom_0x08000000.lds
OUT_BIN_FILE  := $(OUT_FILE_NAME).bin
OUT_ELF_FILE  := $(OUT_FILE_NAME).elf
OUT_MAP_FILE  := $(OUT_FILE_NAME).map
SERVO_TEST_FILE_NAME := servo_test_0x08000000
SERVO_TEST_BIN_FILE  := $(SERVO_TEST_FILE_NAME).bin
SERVO_TEST_ELF_FILE  := $(SERVO_TEST_FILE_NAME).elf
SERVO_TEST_MAP_FILE  := $(SERVO_TEST_FILE_NAME).map

ARCH_FLAGS := -mcpu=cortex-m4 -mthumb -mfpu=fpv4-sp-d16 -mfloat-abi=hard
CPPFLAGS   := -DSTM32F411xE -I.
CFLAGS     := $(ARCH_FLAGS) -std=gnu99 -O3 -Wall -g -fno-builtin \
              -funsigned-char -fno-strict-aliasing -fno-common -MMD -MP
ASFLAGS    := $(ARCH_FLAGS) -x assembler-with-cpp
LDFLAGS    := $(ARCH_FLAGS) --specs=nano.specs --specs=nosys.specs \
              -u _printf_float -nostartfiles -ffreestanding \
              -Wl,-Map=$(OUT_MAP_FILE) -Wl,--cref -Wl,-EL -T $(LDS_FILE_NAME)
LDLIBS     := -lc -lgcc

CSRC := $(filter-out servo_test_main.c,$(wildcard *.c))
ASRC := $(wildcard *.s)
OBJS := $(CSRC:.c=.o) $(ASRC:.s=.o)
SERVO_TEST_OBJS := $(filter-out main.o,$(OBJS)) servo_test_main.o
DEPS := $(OBJS:.o=.d) servo_test_main.d

.PHONY: all clean run servo-test servo-test-run

all: $(OUT_BIN_FILE)

$(OUT_BIN_FILE): $(OUT_ELF_FILE)
	$(OBJCOPY) $< $@ -O binary
	$(OBJDUMP) -x -D $< > __dump.txt
	$(OBJDUMP) -x -D -S $< > __dump_all.txt

$(OUT_ELF_FILE): $(OBJS) $(LDS_FILE_NAME)
	$(CC) $(OBJS) $(LDFLAGS) $(LDLIBS) -o $@

servo-test: $(SERVO_TEST_BIN_FILE)

$(SERVO_TEST_BIN_FILE): $(SERVO_TEST_ELF_FILE)
	$(OBJCOPY) $< $@ -O binary

$(SERVO_TEST_ELF_FILE): $(SERVO_TEST_OBJS) $(LDS_FILE_NAME)
	$(CC) $(SERVO_TEST_OBJS) \
		$(subst $(OUT_MAP_FILE),$(SERVO_TEST_MAP_FILE),$(LDFLAGS)) $(LDLIBS) -o $@

%.o: %.c
	$(CC) $(CPPFLAGS) $(CFLAGS) -c $< -o $@

%.o: %.s
	$(CC) $(CPPFLAGS) $(ASFLAGS) -c $< -o $@

-include $(DEPS)

clean:
	rm -f $(OUT_BIN_FILE) $(OUT_ELF_FILE) $(OUT_MAP_FILE)
	rm -f $(SERVO_TEST_BIN_FILE) $(SERVO_TEST_ELF_FILE) $(SERVO_TEST_MAP_FILE)
	rm -f $(OBJS) servo_test_main.o $(DEPS) __dump.txt __dump_all.txt

run: $(OUT_BIN_FILE)
	@if command -v "$(PROGRAMMER)" >/dev/null 2>&1; then \
		"$(PROGRAMMER)" -c port=SWD -w ./$(OUT_ELF_FILE) -v -rst -q; \
	elif command -v "$(ST_FLASH)" >/dev/null 2>&1; then \
		"$(ST_FLASH)" --reset write ./$(OUT_BIN_FILE) $(FLASH_ADDRESS); \
	else \
		echo "No STM32 programmer found. Install STM32CubeProgrammer or stlink-tools." >&2; \
		exit 127; \
	fi

servo-test-run: $(SERVO_TEST_BIN_FILE)
	@if command -v "$(PROGRAMMER)" >/dev/null 2>&1; then \
		"$(PROGRAMMER)" -c port=SWD -w ./$(SERVO_TEST_ELF_FILE) -v -rst -q; \
	elif command -v "$(ST_FLASH)" >/dev/null 2>&1; then \
		"$(ST_FLASH)" --reset write ./$(SERVO_TEST_BIN_FILE) $(FLASH_ADDRESS); \
	else \
		echo "No STM32 programmer found. Install STM32CubeProgrammer or stlink-tools." >&2; \
		exit 127; \
	fi
