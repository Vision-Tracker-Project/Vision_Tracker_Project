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
extern void Uart2_RX_Interrupt_Enable(int en);


//Led.c
extern void LED_Init(void);
extern void LED_On(void);
extern void LED_Off(void);