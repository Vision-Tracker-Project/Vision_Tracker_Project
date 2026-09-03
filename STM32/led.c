#include "device_driver.h"

void LED_Init(void)
{
	/* 아래 코드 수정 금지 : Port-A Clock Enable */
	Macro_Set_Bit(RCC->AHB1ENR, 0); 

	// LED를 출력으로 설정하고 초기 OFF

	Macro_Write_Block(GPIOA->MODER,0x3,0x1,10);
	Macro_Clear_Bit(GPIOA->OTYPER,5);
    Macro_Clear_Bit(GPIOA->ODR, 5);

}

void LED_On(void)
{
	// LED On
	Macro_Set_Bit(GPIOA->ODR,5);

}

void LED_Off(void)
{
	// LED Off
	Macro_Clear_Bit(GPIOA->ODR,5);

}
