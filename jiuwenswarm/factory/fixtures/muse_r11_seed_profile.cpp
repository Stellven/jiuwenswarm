#include "llama-expert-cache-profile.h"

#include <algorithm>
#include <cstdlib>
#include <iostream>
#include <set>
#include <utility>
#include <vector>

int main(int argc, char ** argv) {
    if (argc != 2) {
        return 1;
    }
    if (llama_expert_cache_profile_enabled(nullptr) ||
        llama_expert_cache_profile_enabled("0") ||
        llama_expert_cache_profile_enabled("true") ||
        !llama_expert_cache_profile_enabled("1")) {
        std::cerr << "Only the exact opt-in enables seeding\n";
        return 1;
    }

    std::vector<std::pair<int, std::vector<int>>> profile;
    if (!llama_expert_cache_profile_parse("profile.json", profile)) {
        std::cerr << "The actual sealed startup profile was refused\n";
        return 1;
    }
    std::set<std::pair<int, int>> experts;
    for (const auto & layer : profile) {
        for (int expert : layer.second) {
            if (layer.first < 0 || expert < 0 || !experts.emplace(layer.first, expert).second) {
                std::cerr << "Layer and expert identities must remain unique and nonnegative\n";
                return 1;
            }
        }
    }
    if (experts.size() != std::strtoul(argv[1], nullptr, 10)) {
        std::cerr << "The production parser did not retain every admitted nomination\n";
        return 1;
    }
    for (const char * path : {"malformed.json", "duplicate.json", "missing.json"}) {
        std::vector<std::pair<int, std::vector<int>>> invalid;
        if (llama_expert_cache_profile_parse(path, invalid)) {
            std::cerr << "Invalid profile accepted: " << path << '\n';
            return 1;
        }
    }

    const std::vector<int> nominees = {7, 2, 5, 19};
    if (llama_expert_cache_profile_admit(nominees, 3, 1) != std::vector<int>{7, 2} ||
        llama_expert_cache_profile_admit(nominees, 10, 1) != nominees ||
        !llama_expert_cache_profile_admit(nominees, 0, 0).empty() ||
        !llama_expert_cache_profile_admit(nominees, 2, 3).empty()) {
        std::cerr << "The admitted nominations must follow profile order and leave the demand reserve\n";
        return 1;
    }
    std::cout << "Gate, sealed profile, invalid inputs and reserved cache capacity passed without a model\n";
    return 0;
}
