#include "device_driver.h"

#define SERVO_PWM_FREQ      50
#define SERVO_TIMER_FREQ    1000000
#define SERVO_PERIOD_US     20000

void TIM2_Servo_Init(void)
{
    // GPIOA Clock Enable
    Macro_Set_Bit(RCC->AHB1ENR, 0);

    // TIM2 Clock Enable
    Macro_Set_Bit(RCC->APB1ENR, 0);

    // --------------------------------------------------------
    // PA0 Alternate Function Mode
    // MODER0 = 10
    // --------------------------------------------------------
    Macro_Write_Block(GPIOA->MODER, 0x3, 0x2, 0);
    Macro_Write_Block(GPIOA->MODER, 0x3, 0x2, 2);
    
    // --------------------------------------------------------
    // PA0 Alternate Function 1
    // PA1 Alternate Function 1 
    // / PA0 → TIM2_CH1 → AF1
    // PA1 → TIM2_CH2 → AF1
    // --------------------------------------------------------
    Macro_Write_Block(GPIOA->AFR[0], 0xF, 0x1, 0);
    Macro_Write_Block(GPIOA->AFR[0], 0xF, 0x1, 4);

    // Push-Pull, No Pull
    Macro_Clear_Bit(GPIOA->OTYPER, 0);
    Macro_Clear_Bit(GPIOA->OTYPER, 1);
    
    Macro_Write_Block(GPIOA->PUPDR, 0xF, 0x0, 0);

    // --------------------------------------------------------
    // TIM2 기본 설정
    // Timer Clock = PCLK1 * 2
    // 1MHz가 되도록 Prescaler 설정
    // --------------------------------------------------------
    TIM2->CR1 = 0;

    TIM2->PSC =
        (unsigned int)((PCLK1 * 2) /
        (double)SERVO_TIMER_FREQ + 0.5) - 1;

    // 20ms 주기 = 50Hz
    TIM2->ARR = SERVO_PERIOD_US - 1;

    // --------------------------------------------------------
    // TIM2_CH1 PWM Mode 1
    //
    // OC1M = 110
    // OC1M = 110
    // CCR Preload 사용 안 함 
    // --------------------------------------------------------
    TIM2->CCMR1 = 0;
    TIM2->CCMR1 |= (0x6 << 4);   // CH1 PWM Mode 1
    TIM2->CCMR1 |= (0x6 << 12 );  // CH2 PWM MODE 1


    // 초기 펄스 폭: 1.5ms
    TIM2->CCR1 = 1000;
    TIM2->CCR2 = 1000;

    // CH1 Output Enable
    TIM2->CCER = 0;
    TIM2->CCER |= (1 << 0);
    TIM2->CCER |= (1 << 4);
    // ARR Preload Enable
    TIM2->CR1 |= (1 << 7);

    // 설정값 즉시 반영
    TIM2->EGR |= (1 << 0);

    // Timer Start
    TIM2->CR1 |= (1 << 0);
}

void TIM2_Servo_Set_Pan_Pulse(unsigned int pulse_ms)
{
    if (pulse_ms < 1000) pulse_ms = 1000;
    if (pulse_ms > 2000) pulse_ms = 2000;

    TIM2->CCR1 = pulse_ms;
}

void TIM2_Servo_Set_Pan_Angle(unsigned int angle)
{
    unsigned int pulse;

    if (angle > 180) angle = 180;

    pulse = 1000 + ((angle * 1000) / 180);
    TIM2->CCR1 = pulse;
}

void TIM2_Servo_Set_Tilt_Pulse(unsigned int pulse_ms)
{
    if (pulse_ms < 1000) pulse_ms = 1000;
    if (pulse_ms > 2000) pulse_ms = 2000;

    TIM2->CCR2 = pulse_ms;
}

void TIM2_Servo_Set_Tilt_Angle(unsigned int angle)
{
    unsigned int pulse;

    if (angle > 180) angle = 180;

    pulse = 1000 + ((angle * 1000) / 180);
    TIM2->CCR2 = pulse;
}