#include "stm32f4xx.h"
#include "option.h"
#include "macro.h"
#include "malloc.h"
#include <stdio.h>

#define PACKET_HEADER 0xAA
#define PACKET_TAIL   0x55
#define PACKET_SIZE   6

// Clock
extern void Clock_Init(void);

// Uart
extern void Uart2_Init(int baud);

extern void Uart2_Send_Byte(char data);
extern void Uart2_RX_Interrupt_Enable(int en);

// LED
extern void LED_Init();

extern void LED_On();
extern void LED_Off();

// servo
extern void TIM2_Servo_Init();

extern void TIM2_Servo_Set_Pan_Angle(unsigned int angle);
extern void TIM2_Servo_Set_Tilt_Angle(unsigned int angle);

extern void TIM2_Servo_Set_Pan_Pulse(unsigned int pulse_ms);
extern void TIM2_Servo_Set_Tilt_Pulse(unsigned int pulse_ms);

// USART2 interrupt handler
extern void USART2_IRQHandler(void);