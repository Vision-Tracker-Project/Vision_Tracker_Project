#include "device_driver.h"


void Uart2_Init(int baud)
{
    double div;
    unsigned int mant;
    unsigned int frac;
    volatile unsigned int t;

    Macro_Set_Bit(RCC->AHB1ENR, 0);                  /* GPIOA clock */
    Macro_Set_Bit(RCC->APB1ENR, 17);                 /* USART2 clock */
    Macro_Write_Block(GPIOA->MODER, 0xf, 0xa, 4);    /* PA2/PA3 alternate */
    Macro_Write_Block(GPIOA->AFR[0], 0xff, 0x77, 8); /* AF7 USART2 */
    Macro_Write_Block(GPIOA->PUPDR, 0xf, 0x5, 4);    /* pull-up */

    t = GPIOA->LCKR & 0x7FFF;
    GPIOA->LCKR = (1u << 16) | t | (3u << 2);
    GPIOA->LCKR = t | (3u << 2);
    GPIOA->LCKR = (1u << 16) | t | (3u << 2);
    t = GPIOA->LCKR;
    (void)t;

    div = PCLK1 / (16.0 * baud);
    mant = (unsigned int)div;
    frac = (unsigned int)((div - mant) * 16.0 + 0.5);
    mant += frac >> 4;
    frac &= 0xf;

    USART2->BRR = (mant << 4) | frac;
    USART2->CR1 = (1u << 13) | (1u << 3) | (1u << 2);
    USART2->CR2 = 0;
    USART2->CR3 = 0;
}

void Uart2_Send_Byte(char data)
{
    if (data == '\n')
    {
        while (!Macro_Check_Bit_Set(USART2->SR, 7));
        USART2->DR = '\r';
    }
    while (!Macro_Check_Bit_Set(USART2->SR, 7));
    USART2->DR = data;
}

void Uart2_Send_String(char *text)
{
    while (*text != 0)
    {
        Uart2_Send_Byte(*text++);
    }
}

void Uart2_RX_Interrupt_Enable(int enabled)
{
    if (enabled)
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
