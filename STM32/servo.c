#include "device_driver.h"

#define SERVO_PWM_FREQ      50
#define SERVO_TIMER_FREQ    1000000
#define SERVO_PERIOD_US     20000
#define SERVO_MIN_PULSE_US  500
#define SERVO_MAX_PULSE_US  2500
#define SERVO_PULSE_RANGE_US (SERVO_MAX_PULSE_US - SERVO_MIN_PULSE_US)




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


    // 팬 초기 펄스 폭: 1.5ms -> 약 90도
    // 틸트 초기 펄스 폭: 0.8ms -> 명령각 약 27도, 카메라 물리각 약 72도
    TIM2->CCR1 = 1500;
    TIM2->CCR2 = 800;

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
