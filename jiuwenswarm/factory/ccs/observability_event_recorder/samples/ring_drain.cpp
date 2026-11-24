// Illustration to adapt. This is not a drop-in patch.
#include <array>
#include <cstddef>

struct ExampleRing {
    // One producer and a drain after quiescence. Entries are toy scalar values.
    std::array<unsigned, 4> entries{};
    std::size_t head = 0;
    std::size_t used = 0;
    std::size_t lost = 0;

    void push(unsigned value) {
        if (used == entries.size()) {
            ++lost;
            return;
        }
        entries[(head + used) % entries.size()] = value;
        ++used;
    }

    // A normal-exit owner calls drain with a sink after producers stop.
    // Sink returns false if a value could not be written.
    template <class Sink>
    void drain(Sink sink) {
        while (used != 0) {
            if (!sink(entries[head])) {
                ++lost;
            }
            head = (head + 1) % entries.size();
            --used;
        }
    }
};
