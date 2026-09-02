#include "device_driver.h"
#include "stm32f4xx.h"
#include "option.h"
#include <stdio.h>
#include <stdarg.h>
#include <string.h>
#include <stdlib.h>
#include <ctype.h>
#include "macro.h"


#define PACKET_SIZE 6
#define PACKET_HEADER 0xAA
#define PACKET_TAIL 0x55

#define TARGET_PAN 0x01
#define TARGET_TILT 0x02


#define ACTION_CR 0x01
#define ACTION_CCR 0x02



static unsigned char packet_buffer[PACKET_SIZE];
static unsigned char packet_index = 0;

// USART2 RX interrupt shared data
volatile unsigned char Uart_Data = 0;
volatile unsigned char Uart_Data_In = 0;

void Uart2_Init(int baud)
{
  double div;
  unsigned int mant;
  unsigned int frac;

  Macro_Set_Bit(RCC->AHB1ENR, 0);                   // PA2,3
  Macro_Set_Bit(RCC->APB1ENR, 17);                   // USART2 ON
  Macro_Write_Block(GPIOA->MODER, 0xf, 0xa, 4);     // PA2,3 => ALT
  Macro_Write_Block(GPIOA->AFR[0], 0xff, 0x77, 8);  // PA2,3 => AF07
  Macro_Write_Block(GPIOA->PUPDR, 0xf, 0x5, 4);     // PA2,3 => Pull-Up  

  volatile unsigned int t = GPIOA->LCKR & 0x7FFF;
  GPIOA->LCKR = (0x1<<16)|t|(0x3<<2);                // Lock PA2, 3 Configuration
  GPIOA->LCKR = (0x0<<16)|t|(0x3<<2);
  GPIOA->LCKR = (0x1<<16)|t|(0x3<<2);
  t = GPIOA->LCKR;

  div = PCLK1/(16. * baud);
  mant = (int)div;
  frac = (int)((div - mant) * 16. + 0.5);
  mant += frac >> 4;
  frac &= 0xf;

  USART2->BRR = (mant<<4)|(frac<<0);
  USART2->CR1 = (1<<13)|(0<<12)|(0<<10)|(1<<3)|(1<<2);
  USART2->CR2 = 0<<12;
  USART2->CR3 = 0;
}

void Uart2_Send_Byte(char data)
{
  if(data == '\n')
  {
    while(!Macro_Check_Bit_Set(USART2->SR, 7));
    USART2->DR = 0x0d;
  }

  while(!Macro_Check_Bit_Set(USART2->SR, 7));
  USART2->DR = data;
}
void Uart2_Send_String(char *pt)
{
    while(*pt != 0)
    {
        Uart2_Send_Byte(*pt++);
    }
}
char Uart2_Get_Pressed(void)
{
    if (USART2->SR & (1 << 5))   // RXNE
    {
        return (char)(USART2->DR & 0xFF);
    }

    return 0;
}

void Uart2_RX_Interrupt_Enable(int en)
{
  if(en)
  {
    Macro_Set_Bit(USART2->CR1, 5);
    NVIC_ClearPendingIRQ(USART2_IRQn);
    NVIC_EnableIRQ(USART2_IRQn);
  }
  else
  {
    Macro_Clear_Bit(USART2->CR1, 5);
    NVIC_DisableIRQ(USART2_IRQn);
  }
}
void Packet_Process(unsigned char *packet)
{
  unsigned char target;
  unsigned char action;
  unsigned char param;
  unsigned char checksum;

  if(packet[0]!= PACKET_HEADER)
  {
    return ;
  }
  if(packet[5]!= PACKET_TAIL)
  {
    return ;
  }
  target=packet[1];
  action=packet[2];
  param=packet[3];
  checksum=packet[4];

  if (checksum != ((target + action + param) & 0xFF))
  {
    Uart2_Send_String("CHECKSUM ERROR");
    return;
  }
    if (target == TARGET_PAN)
    {
        if (action == ACTION_CR)
        {
            TIM2_Servo_Set_Pan_Angle(10);

            // PARAM 1개 = 10ms
            //TIM4_Delay(param * 10);

            //Servo_Stop();

            Uart2_Send_String("DOOR OPEN OK\n");
        }
        else if (action == ACTION_CCR)
        {
             TIM2_Servo_Set_Pan_Angle(0);

            //TIM4_Delay(param * 10);

            //Servo_Stop();

            Uart2_Send_String("DOOR CLOSE OK\n");
        }
    }
    else if (target == TARGET_TILT)
    {
        if (action == ACTION_CR)
        {

        }
        else if (action == ACTION_CCR)
        {

        }

    }

}
void Packet_Receive(void)
{
    unsigned char received_data;


    // 수신 데이터가 없으면 종료
    if (Uart_Data_In == 0)
    {
        return;
    }
    received_data=Uart_Data;

    Uart_Data_In=0;

    // 첫 번째 바이트는 HEADER여야 함
    if (packet_index == 0)
    {
        if (received_data != PACKET_HEADER)
        {
            return;
        }
    }

    packet_buffer[packet_index] = received_data;
    packet_index++;

    // 6바이트 수신 완료
    if (packet_index >= PACKET_SIZE)
    {
        // 마지막 바이트가 TAIL인지 확인
        if (packet_buffer[5] == PACKET_TAIL)
        {
            Packet_Process(packet_buffer);
        }
        else
        {
            Uart2_Send_String("PACKET TAIL ERROR\n");
        }

        // 다음 패킷 수신 준비
        packet_index = 0;
    }
}
