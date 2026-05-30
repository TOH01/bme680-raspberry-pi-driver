#include "bsec_interface.h"
#include "bsec_datatypes.h"
#include "bsec_bridge.h"
#include "bsec_iaq.h"


static void parse_bsec_outputs(const bsec_output_t *bsec_outputs, uint8_t num_bsec_outputs, bsec_result_t *result)
{
    for (uint8_t index = 0; index < num_bsec_outputs; index++) {
        switch (bsec_outputs[index].sensor_id) {
            case BSEC_OUTPUT_IAQ:
                result->iaq = bsec_outputs[index].signal;
                result->iaq_accuracy = bsec_outputs[index].accuracy;
                break;
            case BSEC_OUTPUT_STATIC_IAQ:
                result->static_iaq = bsec_outputs[index].signal;
                break;
            case BSEC_OUTPUT_CO2_EQUIVALENT:
                result->co2_equivalent = bsec_outputs[index].signal;
                break;
            case BSEC_OUTPUT_BREATH_VOC_EQUIVALENT:
                result->breath_voc_equivalent = bsec_outputs[index].signal;
                break;
            case BSEC_OUTPUT_SENSOR_HEAT_COMPENSATED_TEMPERATURE:
                result->temperature = bsec_outputs[index].signal;
                break;
            case BSEC_OUTPUT_SENSOR_HEAT_COMPENSATED_HUMIDITY:
                result->humidity = bsec_outputs[index].signal;
                break;
            case BSEC_OUTPUT_STABILIZATION_STATUS:
                result->stab_status = bsec_outputs[index].signal;
                break;
            case BSEC_OUTPUT_RUN_IN_STATUS:
                result->run_in_status = bsec_outputs[index].signal;
                break;
            case BSEC_OUTPUT_GAS_PERCENTAGE:
                result->gas_percentage = bsec_outputs[index].signal;
                break;
            case BSEC_OUTPUT_COMPENSATED_GAS:
                result->compensated_gas = bsec_outputs[index].signal;
                break;
            default:
                break;
        }
    }
}

static uint8_t prepare_bsec_inputs(bsec_input_t *inputs, uint32_t process_data, float temperature, float humidity, float pressure, float gas_resistance, int64_t timestamp_ns)
{
    uint8_t n_inputs = 0;

    if (process_data & BSEC_PROCESS_TEMPERATURE) {
        inputs[n_inputs].sensor_id  = BSEC_INPUT_TEMPERATURE;
        inputs[n_inputs].signal     = temperature;
        inputs[n_inputs].time_stamp = timestamp_ns;
        n_inputs++;
    }
    if (process_data & BSEC_PROCESS_HUMIDITY) {
        inputs[n_inputs].sensor_id  = BSEC_INPUT_HUMIDITY;
        inputs[n_inputs].signal     = humidity;
        inputs[n_inputs].time_stamp = timestamp_ns;
        n_inputs++;
    }
    if (process_data & BSEC_PROCESS_PRESSURE) {
        inputs[n_inputs].sensor_id  = BSEC_INPUT_PRESSURE;
        inputs[n_inputs].signal     = pressure;
        inputs[n_inputs].time_stamp = timestamp_ns;
        n_inputs++;
    }
    if (process_data & BSEC_PROCESS_GAS) {
        inputs[n_inputs].sensor_id  = BSEC_INPUT_GASRESISTOR;
        inputs[n_inputs].signal     = gas_resistance;
        inputs[n_inputs].time_stamp = timestamp_ns;
        n_inputs++;
    }

    return n_inputs;
}

int BsecBridge_Init(void){
    return bsec_init();
}

int BsecBridge_SetConfiguration(void){
    uint8_t work_buffer[BSEC_MAX_WORKBUFFER_SIZE] = {0};

    return bsec_set_configuration(bsec_config_iaq, sizeof(bsec_config_iaq), work_buffer, BSEC_MAX_WORKBUFFER_SIZE);
}

int BsecBridge_UpdateSubscription(void){
    bsec_sensor_configuration_t requested_virtual_sensors[NUM_USED_OUTPUTS]        = {0};
    bsec_sensor_configuration_t required_sensor_settings[BSEC_MAX_PHYSICAL_SENSOR] = {0};
    uint8_t                     n_requested_virtual_sensors                        = NUM_USED_OUTPUTS;
    uint8_t                     n_required_sensor_settings                         = BSEC_MAX_PHYSICAL_SENSOR;

    requested_virtual_sensors[0].sensor_id = BSEC_OUTPUT_IAQ;
    requested_virtual_sensors[0].sample_rate = BSEC_SAMPLE_RATE_LP;
    requested_virtual_sensors[1].sensor_id = BSEC_OUTPUT_SENSOR_HEAT_COMPENSATED_TEMPERATURE;
    requested_virtual_sensors[1].sample_rate = BSEC_SAMPLE_RATE_LP;
    requested_virtual_sensors[2].sensor_id = BSEC_OUTPUT_SENSOR_HEAT_COMPENSATED_HUMIDITY;
    requested_virtual_sensors[2].sample_rate = BSEC_SAMPLE_RATE_LP;
    requested_virtual_sensors[3].sensor_id = BSEC_OUTPUT_STATIC_IAQ;
    requested_virtual_sensors[3].sample_rate = BSEC_SAMPLE_RATE_LP;
    requested_virtual_sensors[4].sensor_id = BSEC_OUTPUT_CO2_EQUIVALENT;
    requested_virtual_sensors[4].sample_rate = BSEC_SAMPLE_RATE_LP;
    requested_virtual_sensors[5].sensor_id = BSEC_OUTPUT_BREATH_VOC_EQUIVALENT;
    requested_virtual_sensors[5].sample_rate = BSEC_SAMPLE_RATE_LP;
    requested_virtual_sensors[6].sensor_id = BSEC_OUTPUT_STABILIZATION_STATUS;
    requested_virtual_sensors[6].sample_rate = BSEC_SAMPLE_RATE_LP;
    requested_virtual_sensors[7].sensor_id = BSEC_OUTPUT_RUN_IN_STATUS;
    requested_virtual_sensors[7].sample_rate = BSEC_SAMPLE_RATE_LP;
    requested_virtual_sensors[8].sensor_id = BSEC_OUTPUT_GAS_PERCENTAGE;
    requested_virtual_sensors[8].sample_rate = BSEC_SAMPLE_RATE_LP;
    requested_virtual_sensors[9].sensor_id = BSEC_OUTPUT_COMPENSATED_GAS;
    requested_virtual_sensors[9].sample_rate = BSEC_SAMPLE_RATE_LP;

    return bsec_update_subscription(requested_virtual_sensors, n_requested_virtual_sensors, required_sensor_settings, &n_required_sensor_settings);
}

bsec_settings_t BsecBridge_SensorControl(int64_t timestamp_ns)
{
    bsec_settings_t         result   = {0};
    bsec_bme_settings_t     settings = {0};
    bsec_library_return_t   status   = BSEC_OK;
    
    status = bsec_sensor_control(timestamp_ns, &settings);
 
    if (status >= BSEC_OK) {
        result.next_call_ns             = settings.next_call;
        result.heater_temperature       = settings.heater_temperature;
        result.heater_duration          = settings.heater_duration;
        result.run_gas                  = settings.run_gas;
        result.temperature_oversampling = settings.temperature_oversampling;
        result.pressure_oversampling    = settings.pressure_oversampling;
        result.humidity_oversampling    = settings.humidity_oversampling;
        result.trigger_measurement      = settings.trigger_measurement;
        result.process_data             = settings.process_data;
    }
 
    result.status = (int)status;

    return result;
}

bsec_result_t BsecBridge_DoSteps(int64_t timestamp_ns, float temperature, float humidity, float pressure, float gas_resistance, uint32_t process_data)
{
    bsec_library_return_t   status                              = BSEC_OK;
    bsec_result_t           bsec_result                         = {0};
    bsec_output_t           bsec_outputs[BSEC_NUMBER_OUTPUTS]   = {0};
    bsec_input_t            inputs[NUM_USED_INPUTS]             = {0};
    uint8_t                 n_inputs                            = 0;
    uint8_t                 num_bsec_outputs                    = BSEC_NUMBER_OUTPUTS;

    n_inputs = prepare_bsec_inputs(inputs, process_data, temperature, humidity, pressure, gas_resistance, timestamp_ns);

    if (n_inputs == 0) {
        status = BSEC_E_DOSTEPS_INVALIDINPUT;
    }
    if (status == BSEC_OK) {
        status = bsec_do_steps(inputs, n_inputs, bsec_outputs, &num_bsec_outputs);
    }
    if (status >= BSEC_OK) {
        bsec_result.n_outputs = (int)num_bsec_outputs;
        parse_bsec_outputs(bsec_outputs, num_bsec_outputs, &bsec_result);
    }
    
    bsec_result.status = (int)status;
    
    return bsec_result;
}

int BsecBridge_GetState(uint8_t *state_buffer, uint32_t *state_len)
{
    uint8_t work_buffer[BSEC_MAX_WORKBUFFER_SIZE];
    return bsec_get_state(0, state_buffer, BSEC_MAX_STATE_BLOB_SIZE, work_buffer, BSEC_MAX_WORKBUFFER_SIZE, state_len);
}

int BsecBridge_SetState(uint8_t *state_buffer, uint32_t state_len)
{
    uint8_t work_buffer[BSEC_MAX_WORKBUFFER_SIZE];
    return bsec_set_state(state_buffer, state_len, work_buffer, BSEC_MAX_WORKBUFFER_SIZE);
}

uint32_t BsecBridge_GetMaxStateSize(void) 
{ 
    return BSEC_MAX_STATE_BLOB_SIZE; 
}