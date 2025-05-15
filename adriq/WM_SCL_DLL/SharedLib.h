#include "extcode.h"
#ifdef __cplusplus
extern "C" {
#endif

/*!
 * RSet_Feedback
 */
void __cdecl RSet_Feedback(double SCLFeedback[], int32_t len);

MgErr __cdecl LVDLLStatus(char *errStr, int errStrLen, void *module);

void __cdecl SetExecuteVIsInPrivateExecutionSystem(Bool32 value);

#ifdef __cplusplus
} // extern "C"
#endif

