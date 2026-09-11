#include "device_driver.h"

#define SERVO_PWM_FREQ      50
#define SERVO_TIMER_FREQ    1000000
#define SERVO_PERIOD_US     20000
#define SERVO_MIN_PULSE_US  500
#define SERVO_MAX_PULSE_US  2500
#define SERVO_PULSE_RANGE_US (SERVO_MAX_PULSE_US - SERVO_MIN_PULSE_US)

void TIM2_Servo_Pins_Hold_Low(void)
{
    /* GPIOA is available from the reset clock. Drive both signals low as early
       as possible, before either pin is connected to TIM2. */
    Macro_Set_Bit(RCC->AHB1ENR, 0);
    (void)RCC->AHB1ENR;
    GPIOA->BSRR = 0x3u << 16;
    Macro_Write_Block(GPIOA->OTYPER, 0x3, 0x0, 0);
    Macro_Write_Block(GPIOA->PUPDR, 0xF, 0xA, 0);
    Macro_Write_Block(GPIOA->MODER, 0xF, 0x5, 0);
}

void TIM2_Servo_Set_Pan_Pulse(unsigned int pulse_us)
{
    if (pulse_us < SERVO_MIN_PULSE_US) pulse_us = SERVO_MIN_PULSE_US;
    if (pulse_us > SERVO_MAX_PULSE_US) pulse_us = SERVO_MAX_PULSE_US;

    TIM2->CCR1 = pulse_us;
}
void TIM2_Servo_Set_Tilt_Pulse(unsigned int pulse_us)
{
    if (pulse_us < SERVO_MIN_PULSE_US) pulse_us = SERVO_MIN_PULSE_US;
    if (pulse_us > SERVO_MAX_PULSE_US) pulse_us = SERVO_MAX_PULSE_US;

    TIM2->CCR2 = pulse_us;
}
void TIM2_Servo_Set_Pan_Angle(unsigned int angle)
{
    unsigned int pulse;

    if (angle > 180) angle = 180;

    pulse = SERVO_MIN_PULSE_US + ((angle * SERVO_PULSE_RANGE_US) / 180);
    TIM2->CCR1 = pulse;
}

void TIM2_Servo_Set_Tilt_Angle(unsigned int angle)
{
    unsigned int pulse;

    if (angle > 180) angle = 180;

    pulse = SERVO_MIN_PULSE_US + ((angle * SERVO_PULSE_RANGE_US) / 180);
    TIM2->CCR2 = pulse;
}

void TIM2_Servo_Init(void)
{
    /* Keep PA0/PA1 as low GPIO outputs until every TIM2 register is ready. */
    Macro_Set_Bit(RCC->AHB1ENR, 0);
    Macro_Set_Bit(RCC->APB1ENR, 0);
    (void)RCC->APB1ENR;
    TIM2_Servo_Pins_Hold_Low();

    /* Configure the timer with its counter and both outputs disabled. */
    TIM2->CR1 = 0;
    TIM2->CCER = 0;
    TIM2->CNT = 0;

    TIM2->PSC =
        (unsigned int)((PCLK1 * 2) /
        (double)SERVO_TIMER_FREQ + 0.5) - 1;
    TIM2->ARR = SERVO_PERIOD_US - 1;

    /* PWM mode 1 with CCR1/CCR2 preload. Runtime angle changes become
       effective together at the next 20 ms update boundary. */
    TIM2->CCMR1 = (0x6u << 4) | (1u << 3)
                 | (0x6u << 12) | (1u << 11);

    // 팬 초기 펄스 폭: 1.5ms -> 약 90도
    // 틸트 초기 펄스 폭: 0.8ms -> 명령각 약 27도, 카메라 물리각 약 72도
    TIM2->CCR1 = 1500;
    TIM2->CCR2 = 800;
    TIM2->CR1 = 1u << 7;  /* ARR preload, counter still stopped. */
    TIM2->EGR = 1u << 0;  /* Load PSC/ARR/CCR preloads before output. */
    TIM2->SR = 0;

    /* Connect PA0/PA1 to TIM2 only after the waveform is fully defined. */
    Macro_Write_Block(GPIOA->AFR[0], 0xF, 0x1, 0);
    Macro_Write_Block(GPIOA->AFR[0], 0xF, 0x1, 4);
    Macro_Write_Block(GPIOA->OTYPER, 0x3, 0x0, 0);
    Macro_Write_Block(GPIOA->PUPDR, 0xF, 0xA, 0);
    Macro_Write_Block(GPIOA->MODER, 0xF, 0xA, 0);

    TIM2->CCER = (1u << 0) | (1u << 4);
    TIM2->CR1 |= 1u << 0;
}

/* Called by the shared UART parser from main context, never from the ISR. */
void Vehicle_Servo_Command(unsigned int target, unsigned int angle)
{
    if (target == 0x01u)
    {
        TIM2_Servo_Set_Pan_Angle(angle);
    }
    else if (target == 0x02u)
    {
        TIM2_Servo_Set_Tilt_Angle(angle);
    }
}
