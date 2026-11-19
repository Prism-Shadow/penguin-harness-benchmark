#pragma once

#include <cstddef>
#include <cstdint>
#include <cstring>
#include <vector>

using uint = unsigned int;
using uint8_t_alias = std::uint8_t;

class CBuffer
{
public:
    void SetSize(unsigned int size)
    {
        m_data.resize(size);
    }

    void* GetData()
    {
        return m_data.empty() ? nullptr : m_data.data();
    }

private:
    std::vector<std::uint8_t> m_data;
};
