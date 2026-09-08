#include "device_driver.h"

/* MG996R calibration endpoints. Start with the existing 1-2 ms range.
 * Nominal 0/180 commands do not guarantee 180 degrees of physical travel.
 * Adjust only to the pulse range supported by the actual servo.
 */
#define SERVO_TIMER_FREQ    1000000U
#define SERVO_PERIOD_US     20000U
#define SERVO_MIN_PULSE_US  1000U
#define SERVO_MAX_PULSE_US  2000U

static unsigned int Clamp_Pulse(unsigned int pulse_us)
{
    if (pulse_us < SERVO_MIN_PULSE_US) return SERVO_MIN_PULSE_US;
    if (pulse_us > SERVO_MAX_PULSE_US) return SERVO_MAX_PULSE_US;
    return pulse_us;
}

static unsigned int Angle_To_Pulse(unsigned int angle)
{
    if (angle > 180U) angle = 180U;
    return SERVO_MIN_PULSE_US +
        angle * (SERVO_MAX_PULSE_US - SERVO_MIN_PULSE_US) / 180U;
}

/* Keep legacy symbols for uart.c; CH1 output is disabled in this test. */
void TIM2_Servo_Set_Pan_Pulse(unsigned int pulse_us)
{
    TIM2->CCR1 = Clamp_Pulse(pulse_us);
}

void TIM2_Servo_Set_Tilt_Pulse(unsigned int pulse_us)
{
    TIM2->CCR2 = Clamp_Pulse(pulse_us);
}

void TIM2_Servo_Set_Pan_Angle(unsigned int angle)
{
    TIM2->CCR1 = Angle_To_Pulse(angle);
}

void TIM2_Servo_Set_Tilt_Angle(unsigned int angle)
{
    TIM2->CCR2 = Angle_To_Pulse(angle);
}

void TIM2_Servo_Init(void)
{
    Macro_Set_Bit(RCC->AHB1ENR, 0);
    Macro_Set_Bit(RCC->APB1ENR, 0);
    (void)RCC->APB1ENR;

    /* Only PA1: AF1 = TIM2_CH2, push-pull, no pull. */
    Macro_Write_Block(GPIOA->MODER, 0x3, 0x2, 2);
    Macro_Write_Block(GPIOA->AFR[0], 0xF, 0x1, 4);
    Macro_Clear_Bit(GPIOA->OTYPER, 1);
    Macro_Write_Block(GPIOA->PUPDR, 0x3, 0x0, 2);

    TIM2->CR1 = 0;
    TIM2->CCER = 0;
    TIM2->DIER = 0;
    TIM2->PSC = (TIMXCLK / SERVO_TIMER_FREQ) - 1U;
    TIM2->ARR = SERVO_PERIOD_US - 1U;
    TIM2->CNT = 0;
    TIM2->CCMR1 = (0x6U << 12) | (1U << 11); /* CH2 PWM1 + preload */
    TIM2->CCR1 = 0;
    TIM2->CCR2 = Angle_To_Pulse(90U);
    TIM2->CCER = (1U << 4); /* CH2 only, active high */
    TIM2->CR1 = (1U << 7); /* ARR preload */
    TIM2->EGR = 1U;
    TIM2->SR = 0;
    TIM2->CR1 |= 1U;
}
