#include "device_driver.h"
#include "vehicle_hw.h"

#define SERVO_TEST_LOW_ANGLE  70u
#define SERVO_TEST_HIGH_ANGLE 110u
#define SERVO_TEST_CENTER     90u
#define SERVO_TEST_HOLD_MS    1500u

static void Delay_Milliseconds(unsigned milliseconds)
{
    while (milliseconds--)
    {
        while (!(SysTick->CTRL & SysTick_CTRL_COUNTFLAG_Msk))
        {
        }
    }
}

/* UART와 객체 추적을 제외하고 PA0/PA1의 TIM2 PWM만 검증한다. */
void Main(void)
{
    SCB->CPACR |= (0x3u << 20) | (0x3u << 22);
    Clock_Init();
    TIM2_Servo_Init();

    /* Keep both vehicle PWM outputs disabled during this diagnostic. */
    Vehicle_HW_Init();

    TIM2_Servo_Set_Pan_Angle(SERVO_TEST_CENTER);
    TIM2_Servo_Set_Tilt_Angle(SERVO_TEST_CENTER);
    Delay_Milliseconds(SERVO_TEST_HOLD_MS);

    for (;;)
    {
        TIM2_Servo_Set_Pan_Angle(SERVO_TEST_LOW_ANGLE);
        TIM2_Servo_Set_Tilt_Angle(SERVO_TEST_LOW_ANGLE);
        Delay_Milliseconds(SERVO_TEST_HOLD_MS);

        TIM2_Servo_Set_Pan_Angle(SERVO_TEST_HIGH_ANGLE);
        TIM2_Servo_Set_Tilt_Angle(SERVO_TEST_HIGH_ANGLE);
        Delay_Milliseconds(SERVO_TEST_HOLD_MS);
    }
}
