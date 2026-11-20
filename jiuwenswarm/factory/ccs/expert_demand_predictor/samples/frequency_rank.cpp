// Illustration to adapt, not a drop-in patch. Containers here have toy sizes.
#include <algorithm>
#include <map>
#include <set>
#include <utility>
#include <vector>

std::vector<int> rank_examples(const std::vector<std::set<int>> & observed,
                               unsigned limit) {
    std::map<int, unsigned> frequency;
    for (const auto & ids : observed) {
        for (int id : ids) {
            ++frequency[id];
        }
    }

    std::vector<std::pair<int, unsigned>> ranked(frequency.begin(), frequency.end());
    std::sort(ranked.begin(), ranked.end(), [](const auto & left, const auto & right) {
        if (left.second != right.second) {
            return left.second > right.second;
        }
        return left.first < right.first;
    });

    std::vector<int> result;
    for (const auto & entry : ranked) {
        if (result.size() == limit) {
            break;
        }
        result.push_back(entry.first);
    }
    return result;
}
