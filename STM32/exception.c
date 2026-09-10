#include "device_driver.h"
#include "vehicle_hw.h"


void _Invalid_ISR(void)
{
    unsigned int r = Macro_Extract_Area(SCB->ICSR, 0x1ff, 0);
    printf("\nInvalid_Exception: %d!\n", r);
    printf("Invalid_ISR: %d!\n", r - 16);
    for (;;);
}

void USART2_IRQHandler(void)
{
    uint32_t status = USART2->SR;
    if (status & ((1u << 5) | 15u))
    {
        /* Reading DR clears RXNE and captures the byte associated with an
           overrun/framing/noise/parity error for fail-safe handling. */
        uint8_t rx_data = (uint8_t)USART2->DR;
        Vehicle_RX_ISR(status, rx_data);
    }
}
