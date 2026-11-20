// Illustration to adapt. This validates one already-decoded override row.
#include <string>
#include <nlohmann/json.hpp>

bool example_override_row(const nlohmann::json & row) {
    if (!row.is_object() || row.size() != 2 ||
            !row.contains("pattern") || !row.contains("buft")) {
        return false;
    }
    for (const char * key : {"pattern", "buft"}) {
        const auto & field = row.at(key);
        if (!field.is_string()) {
            return false;
        }
        const auto & value = field.get_ref<const std::string &>();
        if (value.empty() || value.find('\0') != std::string::npos) {
            return false;
        }
    }
    // Next resolve the regex and buffer against stock semantics.
    return true;
}

// Parse a bounded stream first. Plain DOM parsing can overwrite duplicate keys.
bool example_document(const std::string & bounded_text) {
    const auto doc = nlohmann::json::parse(bounded_text, nullptr, false);
    return doc.is_object() && doc.contains("overrides") && doc["overrides"].is_array();
}
