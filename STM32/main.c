#include "device_driver.h"

/* Standalone PA1 / TIM2_CH2 servo test. No UART commands required.
 * Nominal angles depend on the calibrated pulse endpoints in servo.c.
 */
#define TEST_STEP_DELAY_MS 20U
#define TEST_HOLD_MS       1000U

static void Delay_Ms(unsigned int milliseconds)
{
    /* Poll SysTick without interrupts; PWM TIM2 keeps running. */
    while (milliseconds-- > 0U)
    {
        while ((SysTick->CTRL & SysTick_CTRL_COUNTFLAG_Msk) == 0U)
        {
        }
    }
}

void Main(void)
{
    unsigned int angle;

    SCB->CPACR |= (0x3U << 20) | (0x3U << 22);
    Clock_Init();
    SysTick->CTRL = 0;
    SysTick->LOAD = (HCLK / 1000U) - 1U;
    SysTick->VAL = 0;
    SysTick->CTRL = SysTick_CTRL_CLKSOURCE_Msk | SysTick_CTRL_ENABLE_Msk;

    TIM2_Servo_Init();
    Delay_Ms(TEST_HOLD_MS);
    for (angle = 90U; angle > 0U; --angle)
    {
        TIM2_Servo_Set_Tilt_Angle(angle - 1U);
        Delay_Ms(TEST_STEP_DELAY_MS);
    }
    for (;;)
    {
        Delay_Ms(TEST_HOLD_MS);
        for (angle = 1U; angle <= 180U; ++angle)
        {
            TIM2_Servo_Set_Tilt_Angle(angle);
            Delay_Ms(TEST_STEP_DELAY_MS);
        }
        Delay_Ms(TEST_HOLD_MS);
        for (angle = 180U; angle > 0U; --angle)
        {
            TIM2_Servo_Set_Tilt_Angle(angle - 1U);
            Delay_Ms(TEST_STEP_DELAY_MS);
        }
    }
}
