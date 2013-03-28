// Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

#ifndef PROP_PROVIDER_H_
#define PROP_PROVIDER_H_

#include <map>
#include <string>

#include <base/basictypes.h>
#include <gestures/gestures.h>

// Declared by gestures library. Implemented here.
// This structure declares virtual overloaded get/set methods to access the
// property value and convert it to different data types.
struct GesturesProp {
  virtual void SetValue(const std::string& value) = 0;

  virtual std::string GetName() = 0;
  virtual ~GesturesProp() {
  }
};

namespace replay {

// The PropProvider class provides a registry for properties. Properties are
// key-value pairs with either int, short, bool, double or string values.
// The properties can be set or read programmatically or parsed from a JSON
// file.
class PropProvider {
 public:
  PropProvider();
  ~PropProvider();

  // Load properties from a JSON string.
  // The object has to consist of a dictionary with numerical or string
  // values. The method will return false if parsing fails due to
  // parsing errors or unknown properties. An error message will be
  // print to std::cerr in this case.
  bool Load(const std::string& data);

  // Create a new property.
  // The loc parameter has to point to the location of this variable.
  // It will be initialized with the value from the parameter init.
  template<typename Type>
  GesturesProp* CreateProp(const char* name, Type* loc, const Type init);

  // Free a previously created property
  void Free(GesturesProp* prop);

  // Check if any loaded properties do not exist in the registry
  bool CheckIntegrity();

 private:
  // Find a property. This method will exit the program and print an
  // error message if the property cannot be found.
  GesturesProp* GetPropSafe(const std::string& name);

  // key-value pair mapping containing all properties.
  std::map<std::string, GesturesProp*> properties_;

  // key-value mapping for properties that are loaded before
  // they were created by gestures.
  std::map<std::string, std::string> properties_cache_;

  DISALLOW_COPY_AND_ASSIGN(PropProvider);
};

// structure containing the function pointer to property creation
// methods. This structure has to be passed to the gestures library to
// access this property provider.
extern GesturesPropProvider CPropProvider;

}  // namespace replay

#endif  // PROP_PROVIDER_H_
