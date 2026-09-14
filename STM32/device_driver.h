#ifndef DEVICE_DRIVER_H
#define DEVICE_DRIVER_H

#include "stm32f4xx.h"
#include "option.h"
#include "macro.h"
#include "malloc.h"
#include <stdio.h>

/* Clock */
extern void Clock_Init(void);

/* USART2: RX is interrupt-driven through Vehicle_RX_ISR. */
extern void Uart2_Init(int baud);
extern void Uart2_Send_Byte(char data);
extern void Uart2_Send_String(char *text);
extern void Uart2_RX_Interrupt_Enable(int enabled);

/* LED */
extern void LED_Off(void);
extern void LED_On(void);
extern void LED_Init(void);

/* TIM2 pan/tilt servo */
extern void TIM2_Servo_Set_Pan_Angle(unsigned int angle);
extern void TIM2_Servo_Set_Tilt_Angle(unsigned int angle);
extern void TIM2_Servo_Pins_Hold_Low(void);
extern void TIM2_Servo_Init(void);
extern void TIM2_Servo_Set_Pan_Pulse(unsigned int pulse_us);
extern void TIM2_Servo_Set_Tilt_Pulse(unsigned int pulse_us);

extern void USART2_IRQHandler(void);

#endif
