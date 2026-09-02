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
    // 수신 버퍼(DR)에 데이터가 들어왔는지 확인 (RXNE 비트)
    if (USART2->SR & (1 << 5))
    {
        // 1. 데이터 레지스터(DR)를 읽으면 수신 인터럽트 플래그가 자동 클리어됩니다.
        char rx_data = (char)(USART2->DR & 0xFF);

        // 2. (테스트용) 받은 데이터를 그대로 젯슨으로 다시 반사 (에코)
        Uart2_Send_Byte(rx_data);
    }
}