#include "Shared/sdk/SharedUtil.AsyncTaskScheduler.h"
#include "Shared/sdk/SharedUtil.AsyncTaskScheduler.hpp"
#include <atomic>
#include <chrono>
#include <thread>
int main() {
#ifdef HAS_ASYNC_TASK_SCHED
    SharedUtil::CAsyncTaskScheduler scheduler(1);
    std::atomic<int> result{-1};
    scheduler.PushTask([] { return 42; }, [&](int value) { result.store(value); });
    for (int i = 0; i < 100 && result.load() < 0; ++i) {
        scheduler.CollectResults();
        std::this_thread::sleep_for(std::chrono::milliseconds(2));
    }
    return result.load() == 42 ? 0 : 1;
#else
    return 1;
#endif
}

