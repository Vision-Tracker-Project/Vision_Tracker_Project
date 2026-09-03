#include "device_driver.h"
#include <stdio.h>
#include<string.h>

#define COMMAND_BUFFER_SIZE 32
#define PACKET_SIZE 6 
#define start 1

static int pan_angle = 90;
static int tilt_angle = 90;

#define SERVO_STEP 10
#define SERVO_MIN_ANGLE 0
#define SERVO_MAX_ANGLE 180

static char command_buffer[COMMAND_BUFFER_SIZE];
static int command_index = 0;
// 함수 원형 선언
static void Command_Process(char *command);
static void Command_Receive(void);


static void Sys_Init(int baud) 
{
	SCB->CPACR |= (0x3 << 10*2)|(0x3 << 11*2); 
	Clock_Init();
	Uart2_Init(baud);
	setvbuf(stdout, NULL, _IONBF, 0);
	LED_Init();
}

void Main(void)
{
    Sys_Init(115200);

    // TIM2_CH1 / PA0 서보 PWM 초기화
    TIM2_Servo_Init();
    //Uart2_RX_Interrupt_Enable(start);

    Uart2_Send_String(
		"SYSTME READY\r\n"

        "\r\n============================\r\n"
        " STM32 CAMERA Control Test\r\n"
        " $PU : Pan Up\r\n"
        " $PD : Pan Down\r\n"
        " $TU : Tilt Up\r\n"
        " $TD : Tilt Down TT\r\n"
        "============================\r\n"
    );

    for (;;)
    {
        Command_Receive();
		//Packet_Receive();
    }
}

// ------------------------------------------------------------
// UART 명령 수신
// ------------------------------------------------------------
static void Command_Receive(void)
{
    char received_char;

    received_char = Uart2_Get_Pressed();

    if (received_char == 0)
    {
        return;
    }

    if (received_char == '\r' ||
        received_char == '\n')
    {
        if (command_index > 0)
        {
            command_buffer[command_index] = '\0';

            Uart2_Send_Byte('\n');
            Uart2_Send_String("RX: ");
            Uart2_Send_String(command_buffer);
            Uart2_Send_Byte('\n');

            Command_Process(command_buffer);

            command_index = 0;
            command_buffer[0] = '\0';
        }

        return;
    }

    if (received_char == '\b')
    {
        if (command_index > 0)
        {
            command_index--;
            command_buffer[command_index] = '\0';

            Uart2_Send_String("\b \b");
        }

        return;
    }

    if (command_index < COMMAND_BUFFER_SIZE - 1)
    {
        command_buffer[command_index++] = received_char;

        // Tera Term 에코
        Uart2_Send_Byte(received_char);
    }
}


// ------------------------------------------------------------
// 명령 처리
// ------------------------------------------------------------
static void Command_Process(char *command)
{
    if (strcmp(command, "$PU") == 0)
    {
        pan_angle += SERVO_STEP;

        if (pan_angle > SERVO_MAX_ANGLE)
            pan_angle = SERVO_MAX_ANGLE;

        TIM2_Servo_Set_Pan_Angle((unsigned int)pan_angle);

        Uart2_Send_String("$ACK,PAN,UP\n");
    }
    else if (strcmp(command, "$PD") == 0)
    {
        pan_angle -= SERVO_STEP;

        if (pan_angle < SERVO_MIN_ANGLE)
            pan_angle = SERVO_MIN_ANGLE;

        TIM2_Servo_Set_Pan_Angle((unsigned int)pan_angle);

        Uart2_Send_String("$ACK,PAN,DOWN\n");
    }
    else if (strcmp(command, "$TU") == 0)
    {
        tilt_angle += SERVO_STEP;

        if (tilt_angle > SERVO_MAX_ANGLE)
            tilt_angle = SERVO_MAX_ANGLE;

        TIM2_Servo_Set_Tilt_Angle((unsigned int)tilt_angle);

        Uart2_Send_String("$ACK,TILT,UP\n");
    }
    else if (strcmp(command, "$TD") == 0)
    {
        tilt_angle -= SERVO_STEP;

        if (tilt_angle < SERVO_MIN_ANGLE)
            tilt_angle = SERVO_MIN_ANGLE;

        TIM2_Servo_Set_Tilt_Angle((unsigned int)tilt_angle);

        Uart2_Send_String("$ACK,TILT,DOWN\n");
    }
    else if (strcmp(command, "$HELP") == 0)
    {
        Uart2_Send_String(
            "$PU : Pan Up\n"
            "$PD : Pan Down\n"
            "$TU : Tilt Up\n"
            "$TD : Tilt Down\n"
        );
    }
    else
    {
        Uart2_Send_String("$NACK,UNKNOWN_COMMAND\n");
    }
}