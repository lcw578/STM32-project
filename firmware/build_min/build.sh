#!/usr/bin/env bash
# 最小构建脚本：用 CubeIDE 自带 arm-none-eabi-gcc + STM32Cube_FW_F1 HAL 编译固件
# 产物：build_min/fw.hex（用于 STM32_Programmer_CLI 烧录）
set -e
cd "$(dirname "$0")"

TC="D:/STM32/STM32CubeIDE_1.19.0/STM32CubeIDE/plugins/com.st.stm32cube.ide.mcu.externaltools.gnu-tools-for-stm32.13.3.rel1.win32_1.0.0.202411081344/tools/bin"
CC="$TC/arm-none-eabi-gcc.exe"
OBJCOPY="$TC/arm-none-eabi-objcopy.exe"
FW="C:/Users/33178/STM32Cube/Repository/STM32Cube_FW_F1_V1.8.7"
CORE="E:/STM32_design/firmware/Core"

FLAGS="-mcpu=cortex-m3 -mthumb -O2 -g3 -ffunction-sections -fdata-sections"
DEFS="-DSTM32F103xB -DUSE_HAL_DRIVER"
INC="-I$CORE/Inc -I. \
 -I$FW/Drivers/STM32F1xx_HAL_Driver/Inc \
 -I$FW/Drivers/CMSIS/Device/ST/STM32F1xx/Include \
 -I$FW/Drivers/CMSIS/Include"

HAL="$FW/Drivers/STM32F1xx_HAL_Driver/Src"
SRCS="$CORE/Src/main.c $CORE/Src/bsp_power.c $CORE/Src/control.c $CORE/Src/cli.c \
 $HAL/stm32f1xx_hal.c $HAL/stm32f1xx_hal_adc.c $HAL/stm32f1xx_hal_adc_ex.c \
 $HAL/stm32f1xx_hal_cortex.c $HAL/stm32f1xx_hal_dma.c $HAL/stm32f1xx_hal_flash.c \
 $HAL/stm32f1xx_hal_flash_ex.c $HAL/stm32f1xx_hal_gpio.c $HAL/stm32f1xx_hal_rcc.c \
 $HAL/stm32f1xx_hal_rcc_ex.c $HAL/stm32f1xx_hal_uart.c \
 system_stm32f1xx.c stm32f1xx_it.c stm32f1xx_hal_msp.c startup_stm32f103xb.s"

rm -rf obj && mkdir -p obj
OBJS=()
for s in $SRCS; do
  o="obj/$(basename "${s%.*}").o"
  echo "CC $(basename "$s")"
  "$CC" $FLAGS $DEFS $INC -x assembler-with-cpp -c "$s" -o "$o" 2>/dev/null || \
  "$CC" $FLAGS $DEFS $INC -c "$s" -o "$o"
  OBJS+=("$o")
done

echo "LINK fw.elf"
"$CC" $FLAGS -T"$FW/Drivers/CMSIS/Device/ST/STM32F1xx/Source/Templates/gcc/linker/STM32F103XB_FLASH.ld" \
  -Wl,--gc-sections -Wl,-Map=fw.map -specs=nano.specs -specs=nosys.specs \
  -u _printf_float \
  "${OBJS[@]}" -o fw.elf -lm -lc -lnosys

"$OBJCOPY" -O ihex fw.elf fw.hex
"$OBJCOPY" -O binary fw.elf fw.bin
echo "SIZE:"
"$TC/arm-none-eabi-size.exe" fw.elf
echo "OK: build_min/fw.hex"
