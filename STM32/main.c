#include "device_driver.h"
#include "vehicle_hw.h"

void Main(void)
{
    SCB->CPACR |= (0x3 << 10*2) | (0x3 << 11*2);

    /* Keep servo inputs quiet while the system clock and TIM2 are configured. */
    TIM2_Servo_Pins_Hold_Low();
    Clock_Init();

    /* TIM2 owns the independent pan/tilt outputs; TIM3 owns both drive PWMs. */
    TIM2_Servo_Init();
    Vehicle_HW_Init();

    /* One USART2 receive path parses both the 6-byte servo frames and the
       8-byte vehicle frames. */
    Uart2_Init(115200);

    Uart2_RX_Interrupt_Enable(1);
    
    for (;;)
    {
        Vehicle_HW_Poll();
    }
}
