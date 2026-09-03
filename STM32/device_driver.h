#include "stm32f4xx.h"
#include "option.h"
#include "macro.h"
#include "malloc.h"
#include <stdio.h>

// Clock
extern void Clock_Init(void);

// Uart
extern void Uart2_Init(int baud);
extern void Uart2_Send_Byte(char data);
extern void Uart2_Send_String(char *pt);
extern char Uart2_Get_Pressed(void);
extern void Uart2_RX_Interrupt_Enable(int en);
extern void Uart2_RX_Push_From_ISR(unsigned char data);
extern void Packet_Receive(void);

// LED
extern void LED_Off();
extern void LED_On();
extern void LED_Init();

// servo

extern void Servo_Close_Direction();
extern void TIM2_Servo_Set_Pan_Angle(unsigned int angle);
extern void TIM2_Servo_Set_Tilt_Angle(unsigned int angle);
extern void TIM2_Servo_Init();
extern void TIM2_Servo_Set_Pan_Pulse(unsigned int pulse_us);
extern void TIM2_Servo_Set_Tilt_Pulse(unsigned int pulse_us);

// USART2 interrupt handler
extern void USART2_IRQHandler(void);



