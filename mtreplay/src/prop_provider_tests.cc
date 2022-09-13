// Copyright 2012 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

#include <gtest/gtest.h>

#include "prop_provider.h"

namespace replay {
/*
TODO(denniskempin): Re-implement programmatic access to properties

class PropProviderTests: public ::testing::Test {
};

TEST(PropProviderTests, SimplePropertySetGet) {
  int propertyValue = 0;

  PropProvider provider;
  CPropProvider.create_int_fn(&provider, "TheAnswer", &propertyValue, 23);

  EXPECT_EQ(propertyValue, 23);
  EXPECT_EQ(provider.GetValue<int>("TheAnswer"), 23);

  provider.SetValue("TheAnswer", 42);
  EXPECT_EQ(propertyValue, 42);
  EXPECT_EQ(provider.GetValue<int>("TheAnswer"), 42);
}

TEST(PropProviderTests, SimplePropertyIntegralConversion) {
  int intValue = 0;
  double doubleValue = 0;
  short shortValue = 0;
  GesturesPropBool boolValue = false;

  PropProvider provider;
  CPropProvider.create_int_fn(&provider, "int", &intValue, 0);
  CPropProvider.create_short_fn(&provider, "short", &shortValue, 0);
  CPropProvider.create_real_fn(&provider, "double", &doubleValue, 0);
  CPropProvider.create_bool_fn(&provider, "bool", &boolValue, 0);

  provider.SetValue("int", 42.9);
  provider.SetValue("short", 42.9);
  provider.SetValue("double", 42.9);
  provider.SetValue("bool", 42.9);
  EXPECT_EQ(provider.GetValue<int>("int"), 42);
  EXPECT_EQ(provider.GetValue<short>("short"), 42);
  EXPECT_EQ(provider.GetValue<double>("double"), 42.9);
  EXPECT_EQ(provider.GetValue<bool>("bool"), true);

  provider.SetValue("int", 42);
  provider.SetValue("short", 42);
  provider.SetValue("double", 42);
  provider.SetValue("bool", 42);
  EXPECT_EQ(provider.GetValue<int>("int"), 42);
  EXPECT_EQ(provider.GetValue<short>("short"), 42);
  EXPECT_EQ(provider.GetValue<double>("double"), 42.0);
  EXPECT_EQ(provider.GetValue<bool>("bool"), true);

  provider.SetValue("int", true);
  provider.SetValue("short", true);
  provider.SetValue("double", true);
  provider.SetValue("bool", true);
  EXPECT_EQ(provider.GetValue<int>("int"), 1);
  EXPECT_EQ(provider.GetValue<short>("short"), 1);
  EXPECT_EQ(provider.GetValue<double>("double"), 1.0);
  EXPECT_EQ(provider.GetValue<bool>("bool"), true);
}

TEST(PropProviderTests, SimplePropertyStringToIntegralConversion) {
  int intValue = 0;
  double doubleValue = 0;
  short shortValue = 0;
  GesturesPropBool boolValue = false;

  PropProvider provider;
  CPropProvider.create_int_fn(&provider, "int", &intValue, 0);
  CPropProvider.create_short_fn(&provider, "short", &shortValue, 0);
  CPropProvider.create_real_fn(&provider, "double", &doubleValue, 0);
  CPropProvider.create_bool_fn(&provider, "bool", &boolValue, 0);

  provider.SetValue("int", std::string("42.9"));
  provider.SetValue("short", std::string("42.9"));
  provider.SetValue("double", std::string("42.9"));
  provider.SetValue("bool", std::string("42.9"));
  EXPECT_EQ(provider.GetValue<int>("int"), 42);
  EXPECT_EQ(provider.GetValue<short>("short"), 42);
  EXPECT_EQ(provider.GetValue<double>("double"), 42.9);
  EXPECT_EQ(provider.GetValue<bool>("bool"), true);

  provider.SetValue("int", std::string("42"));
  provider.SetValue("short", std::string("42"));
  provider.SetValue("double", std::string("42"));
  provider.SetValue("bool", std::string("42"));
  EXPECT_EQ(provider.GetValue<int>("int"), 42);
  EXPECT_EQ(provider.GetValue<short>("short"), 42);
  EXPECT_EQ(provider.GetValue<double>("double"), 42.0);
  EXPECT_EQ(provider.GetValue<bool>("bool"), true);

  provider.SetValue("int", std::string("true"));
  provider.SetValue("short", std::string("true"));
  provider.SetValue("double", std::string("false"));
  provider.SetValue("bool", std::string("false"));
  EXPECT_EQ(provider.GetValue<int>("int"), 1);
  EXPECT_EQ(provider.GetValue<short>("short"), 1);
  EXPECT_EQ(provider.GetValue<double>("double"), 0.0);
  EXPECT_EQ(provider.GetValue<bool>("bool"), false);
}

TEST(PropProviderTests, StringGetSet) {
  const char* value = 0;

  PropProvider provider;
  CPropProvider.create_string_fn(&provider, "string", &value, "Initial");

  EXPECT_EQ(provider.GetValue<std::string>("string"), "Initial");

  provider.SetValue("string", std::string("New"));
  EXPECT_EQ(provider.GetValue<std::string>("string"), "New");
}

TEST(PropProviderTests, JSONProperties) {
  int intValue = 0;
  double doubleValue = 0;
  short shortValue = 0;
  GesturesPropBool boolValue = false;
  const char* stringValue;

  PropProvider provider;
  CPropProvider.create_int_fn(&provider, "int", &intValue, 0);
  CPropProvider.create_short_fn(&provider, "short", &shortValue, 0);
  CPropProvider.create_real_fn(&provider, "double", &doubleValue, 0);
  CPropProvider.create_bool_fn(&provider, "bool", &boolValue, 0);
  CPropProvider.create_string_fn(&provider, "string", &stringValue, "");

  std::string json = "{"
      "\"int\": 42,"
      "\"short\": 42,"
      "\"double\": 42.9,"
      "\"bool\": true,"
      "\"string\": \"New\""
      "}";

  bool result = provider.Load(json);
  ASSERT_TRUE(result);
  EXPECT_EQ(provider.GetValue<int>("int"), 42);
  EXPECT_EQ(provider.GetValue<short>("short"), 42);
  EXPECT_EQ(provider.GetValue<double>("double"), 42.9);
  EXPECT_EQ(provider.GetValue<bool>("bool"), true);
  EXPECT_EQ(provider.GetValue<std::string>("string"), "New");
}

// Deactivate test for now. It's been broken for a while now.
// TODO(denniskempin): fix test
TEST(PropProviderTests, DISABLED_GesturesGetSet) {
  PropProvider provider;

  GestureInterpreter* interpreter = new GestureInterpreter(1);
  interpreter->SetPropProvider(&CPropProvider, &provider);

  // Just probe one property
  provider.SetValue("Tap Enable", true);
  EXPECT_EQ(provider.GetValue<bool>("Tap Enable"), true);
}
*/
}  // namespace replay
