#include "device_driver.h"

#define PACKET_SIZE 6U
#define PACKET_HEADER 0xAAU
#define PACKET_TAIL 0x55U

#define TARGET_PAN 0x01U
#define TARGET_TILT 0x02U
#define ACTION_SET_ANGLE 0x01U
#define SERVO_MAX_ANGLE 180U

#define UART_RX_BUFFER_SIZE 64U

static unsigned char packet_buffer[PACKET_SIZE];
static unsigned char packet_index = 0U;

static volatile unsigned char uart_rx_buffer[UART_RX_BUFFER_SIZE];
static volatile unsigned int uart_rx_head = 0U;
static volatile unsigned int uart_rx_tail = 0U;

void Uart2_Init(int baud)
{
    double div;
    unsigned int mant;
    unsigned int frac;
    volatile unsigned int t;

    Macro_Set_Bit(RCC->AHB1ENR, 0);
    Macro_Set_Bit(RCC->APB1ENR, 17);
    Macro_Write_Block(GPIOA->MODER, 0xf, 0xa, 4);
    Macro_Write_Block(GPIOA->AFR[0], 0xff, 0x77, 8);
    Macro_Write_Block(GPIOA->PUPDR, 0xf, 0x5, 4);

    t = GPIOA->LCKR & 0x7FFF;
    GPIOA->LCKR = (0x1U << 16) | t | (0x3U << 2);
    GPIOA->LCKR = (0x0U << 16) | t | (0x3U << 2);
    GPIOA->LCKR = (0x1U << 16) | t | (0x3U << 2);
    t = GPIOA->LCKR;
    (void)t;

    div = PCLK1 / (16.0 * baud);
    mant = (unsigned int)div;
    frac = (unsigned int)((div - mant) * 16.0 + 0.5);
    mant += frac >> 4;
    frac &= 0xfU;

    USART2->BRR = (mant << 4) | frac;
    USART2->CR1 = (1U << 13) | (1U << 3) | (1U << 2);
    USART2->CR2 = 0U;
    USART2->CR3 = 0U;
}

void Uart2_Send_Byte(char data)
{
    if (data == '\n')
    {
        while (!Macro_Check_Bit_Set(USART2->SR, 7));
        USART2->DR = 0x0d;
    }

    while (!Macro_Check_Bit_Set(USART2->SR, 7));
    USART2->DR = (unsigned char)data;
}

void Uart2_Send_String(char *pt)
{
    while (*pt != 0)
    {
        Uart2_Send_Byte(*pt++);
    }
}

char Uart2_Get_Pressed(void)
{
    if (USART2->SR & (1U << 5))
    {
        return (char)(USART2->DR & 0xFFU);
    }

    return 0;
}

void Uart2_RX_Interrupt_Enable(int en)
{
    if (en)
    {
        Macro_Set_Bit(USART2->CR1, 5);
        NVIC_ClearPendingIRQ(USART2_IRQn);
        NVIC_EnableIRQ(USART2_IRQn);
    }
    else
    {
        Macro_Clear_Bit(USART2->CR1, 5);
        NVIC_DisableIRQ(USART2_IRQn);
    }
}

void Uart2_RX_Push_From_ISR(unsigned char data)
{
    unsigned int next_head = (uart_rx_head + 1U) % UART_RX_BUFFER_SIZE;

    if (next_head != uart_rx_tail)
    {
        uart_rx_buffer[uart_rx_head] = data;
        uart_rx_head = next_head;
    }
}

static int Uart2_Read_Byte(unsigned char *data)
{
    if (uart_rx_head == uart_rx_tail)
    {
        return 0;
    }

    *data = uart_rx_buffer[uart_rx_tail];
    uart_rx_tail = (uart_rx_tail + 1U) % UART_RX_BUFFER_SIZE;
    return 1;
}

static void Uart2_Send_Raw(const unsigned char *data, unsigned int length)
{
    unsigned int i;

    for (i = 0U; i < length; i++)
    {
        while (!Macro_Check_Bit_Set(USART2->SR, 7));
        USART2->DR = data[i];
    }
}

static int Packet_Process(const unsigned char *packet)
{
    unsigned char target = packet[1];
    unsigned char action = packet[2];
    unsigned char angle = packet[3];
    unsigned char checksum = packet[4];

    if (packet[0] != PACKET_HEADER || packet[5] != PACKET_TAIL)
    {
        return 0;
    }

    if (checksum != (unsigned char)(target + action + angle))
    {
        return 0;
    }

    if (action != ACTION_SET_ANGLE || angle > SERVO_MAX_ANGLE)
    {
        return 0;
    }

    if (target == TARGET_PAN)
    {
        TIM2_Servo_Set_Pan_Angle(angle);
    }
    else if (target == TARGET_TILT)
    {
        TIM2_Servo_Set_Tilt_Angle(angle);
    }
    else
    {
        return 0;
    }

    Uart2_Send_Raw(packet, PACKET_SIZE);
    return 1;
}

void Packet_Receive(void)
{
    unsigned char received_data;

    while (Uart2_Read_Byte(&received_data))
    {
        if (packet_index == 0U && received_data != PACKET_HEADER)
        {
            continue;
        }

        packet_buffer[packet_index++] = received_data;

        if (packet_index == PACKET_SIZE)
        {
            Packet_Process(packet_buffer);
            packet_index = 0U;
        }
    }
}
