#include "device_driver.h"

void Main(void)
{
    SCB->CPACR |= (0x3 << 10*2)|(0x3 << 11*2); 
    Clock_Init();
    Uart2_Init(115200);
    Uart2_RX_Interrupt_Enable(1);

    printf("test !\n");

    for(;;)
    {

    }
}