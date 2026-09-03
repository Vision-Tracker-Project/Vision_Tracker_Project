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
    if (Macro_Check_Bit_Set(USART2->SR, 5))
    {
        Uart2_RX_Push_From_ISR((unsigned char)(USART2->DR & 0xFFU));
    }
}
