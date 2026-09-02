#include "device_driver.h"


void _Invalid_ISR(void)
{
	unsigned int r = Macro_Extract_Area(SCB->ICSR, 0x1ff, 0);
	printf("\nInvalid_Exception: %d!\n", r);
	printf("Invalid_ISR: %d!\n", r - 16);
	for(;;);
}

void USART2_IRQHandler(void)
{
    // RXNE(수신 데이터 준비)인 경우에만 DR을 읽습니다.
    // DR을 읽으면 RXNE가 클리어됩니다.
    if (Macro_Check_Bit_Set(USART2->SR, 5))
    {
        Uart_Data = (unsigned char)(USART2->DR & 0xFF);
        Uart_Data_In = 1;
    }
}
