#include <algorithm>

#ifndef ADA_PROBE_HAS_LENGTH_LIMIT
#error ADA_PROBE_HAS_LENGTH_LIMIT must come from the compiler capability check
#endif

template <class Url>
static constexpr bool has_href_size = requires(const Url& value) {
  value.get_href_size();
};

template <class Url>
static bool href_size_agrees(const Url& value) {
  if constexpr (has_href_size<Url>) {
    return value.get_href_size() == value.get_href().size();
  }
  return true;
}

static int length_cases() {
#if ADA_PROBE_HAS_LENGTH_LIMIT
  struct restore_limit {
    uint32_t previous = ada::get_max_input_length();
    ~restore_limit() { ada::set_max_input_length(previous); }
  } restore;
  const std::vector<std::pair<std::string, std::string>> cases{
      {"https://e.test/", "https://e.test/"},
      {"https://e.test/a b", "https://e.test/a%20b"},
      {"https://e.test/é", "https://e.test/%C3%A9"},
      {"http://e.test:80/", "http://e.test/"},
      {"https://e.test/" + std::string(49, 'x'),
       "https://e.test/" + std::string(49, 'x')}};
  for (const auto& [input, expected] : cases) {
    const auto boundary = static_cast<uint32_t>(std::max(input.size(), expected.size()));
    for (uint32_t limit : {boundary - 1, boundary, boundary + 1}) {
      ada::set_max_input_length(limit);
      if (ada::get_max_input_length() != limit) return 10;
      const bool accepted = limit >= boundary;
      auto parsed = ada::parse<ada::url>(input);
      auto aggregated = ada::parse<ada::url_aggregator>(input);
      if (bool(parsed) != accepted || bool(aggregated) != accepted) return 11;
      if (ada::can_parse(input) != accepted) return 12;
      if (accepted && (parsed->get_href() != expected ||
                       aggregated->get_href() != expected)) return 13;
    }
  }
  for (uint32_t limit : {24, 37, 24}) {
    ada::set_max_input_length(limit);
    if (!ada::parse<ada::url>("https://e.test/") ||
        !ada::parse<ada::url_aggregator>("https://e.test/")) return 14;
    const std::string long_input = "https://e.test/" + std::string(limit, 'q');
    if (ada::parse<ada::url>(long_input) ||
        ada::parse<ada::url_aggregator>(long_input) ||
        ada::can_parse(long_input)) return 15;
  }
#endif
  return 0;
}

template <class Url>
static int serialization_cases() {
  for (const std::string& input : std::vector<std::string>{
           "https://example.com/path?x#y", "https://éxample.com/a b",
           "file:///a/b", "non-special:opaque/path"}) {
    auto parsed = ada::parse<Url>(input);
    if (!parsed || !href_size_agrees(*parsed)) return 20;
    parsed->set_search("?changed=é");
    if (!href_size_agrees(*parsed)) return 21;
    parsed->set_hash("#next");
    if (!href_size_agrees(*parsed)) return 22;
    parsed->set_search("");
    parsed->set_hash("");
    if (!href_size_agrees(*parsed)) return 23;
  }
  return 0;
}

static int ordered_capture_cases() {
  const std::vector<std::vector<std::string>> names{
      {"a", "b"}, {"z", "a"}, {"only"},
      {"zulu", "alpha", "middle", "beta", "last", "first", "tail", "head",
       "item9", "item8", "item7", "item6", "item5", "item4", "item3", "item2"}};
  for (const auto& keys : names) {
    auto init = ada::url_pattern_init{};
    std::string pattern;
    for (const auto& key : keys) pattern += "/:" + key;
    init.pathname = pattern;
    auto parsed = ada::parse_url_pattern<provider>(init);
    if (!parsed) return 1;
    for (const std::string& prefix : {std::string("value"), std::string("again")}) {
      std::string input;
      std::vector<std::string> values;
      for (size_t index = 0; index < keys.size(); ++index) {
        values.push_back(prefix + std::to_string(index));
        input += "/" + values.back();
      }
      auto initializer = ada::url_pattern_init{};
      initializer.pathname = input;
      auto result = parsed->exec(initializer, nullptr);
      if (!result || !result->has_value()) return 2;
      const auto& groups = result->value().pathname.groups;
      if (groups.size() != keys.size()) return 3;
      size_t index = 0;
      for (const auto& [key, value] : groups) {
        if (index >= keys.size() || key != keys[index] || group_unset(value) ||
            group_value(value) != values[index]) return 4;
        auto found = groups.find(key);
        if (found == groups.end() || group_value(found->second) != values[index]) return 5;
        ++index;
      }
      if (index != keys.size() || groups.find("absent") != groups.end()) return 6;
      initializer.pathname = input + "/extra";
      auto rejected = parsed->exec(initializer, nullptr);
      if (!rejected || rejected->has_value()) return 7;
      std::string next_input;
      for (size_t next_index = 0; next_index < keys.size(); ++next_index) {
        next_input += "/later" + std::to_string(next_index);
      }
      initializer.pathname = next_input;
      auto next_result = parsed->exec(initializer, nullptr);
      if (!next_result || !next_result->has_value()) return 12;
      index = 0;
      for (const auto& [key, value] : groups) {
        if (index >= keys.size() || key != keys[index] ||
            group_value(value) != values[index]) return 13;
        ++index;
      }
      if (index != keys.size()) return 14;
    }
  }
  auto init = ada::url_pattern_init{};
  init.pathname = "/:a/:b";
  auto parsed = ada::parse_url_pattern<provider>(init);
  if (!parsed) return 8;
  auto input = ada::url_pattern_init{};
  input.pathname = "/x/y";
  auto result = parsed->exec(input, nullptr);
  if (!result || !result->has_value()) return 9;
  const auto& groups = result->value().pathname.groups;
  const std::vector<std::pair<std::string, std::string>> expected{{"a", "x"}, {"b", "y"}};
  size_t index = 0;
  for (const auto& [key, value] : groups) {
    if (index >= expected.size() || key != expected[index].first ||
        group_value(value) != expected[index].second) return 10;
    ++index;
  }
  return index == expected.size() ? 0 : 11;
}
