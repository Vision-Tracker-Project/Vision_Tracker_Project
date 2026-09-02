#include "device_driver.h"

void Main(void)
{
    Clock_Init();
    Uart2_Init(115200);
    Uart2_RX_Interrupt_Enable(1);

    printf("test !\n");

    for(;;)
    {

    }
}