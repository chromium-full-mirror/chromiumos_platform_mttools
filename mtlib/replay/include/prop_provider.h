// Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

#ifndef PROP_PROVIDER_H_
#define PROP_PROVIDER_H_

#include <string>
#include <map>

#include <base/basictypes.h>
#include <gestures/gestures.h>

#include <generic_stream.h>

// Declared by gestures library. Implemented here.
// This structure declares virtual overloaded get/set methods to access the
// property value and convert it to different data types.
struct GesturesProp {
  virtual void SetValue(int value) = 0;
  virtual void SetValue(short value) = 0;
  virtual void SetValue(bool value) = 0;
  virtual void SetValue(double value) = 0;
  virtual void SetValue(const std::string& value) = 0;
  virtual void GetValue(int* value) = 0;
  virtual void GetValue(short* value) = 0;
  virtual void GetValue(bool* value) = 0;
  virtual void GetValue(double* value) = 0;
  virtual void GetValue(std::string* value) = 0;

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

  // Load properties from a JSON file.
  // See LoadString.
  bool Load(GenericIStream* stream);

  // Load properties from a JSON string.
  // The object has to consist of a dictionary with numerical or string
  // values. The method will return false if parsing fails due to
  // parsing errors or unknown properties. An error message will be
  // print to std::cerr in this case.
  bool LoadString(const std::string& data);

  // Create a new property.
  // The loc parameter has to point to the location of this variable.
  // It will be initialized with the value from the parameter init.
  template<typename Type>
  GesturesProp* CreateProp(const char* name, Type* loc, const Type init);

  // Free a previously created property
  void Free(GesturesProp* prop);

  // Set a property to a value of any supported type. The value will
  // automatically be converted to the type of the property.
  template<typename Type>
  void SetValue(const std::string& name, Type value) {
    GetPropSafe(name)->SetValue(value);
  }

  // Read a property value and convert it to one of the supported types.
  template<typename Type>
  Type GetValue(const std::string& name) {
    Type value;
    GetPropSafe(name)->GetValue(&value);
    return value;
  }

 private:
  DISALLOW_COPY_AND_ASSIGN(PropProvider);

  // Find a property. This method will exit the program and print an
  // error message if the property cannot be found.
  GesturesProp* GetPropSafe(const std::string& name);

  // key-value pair mapping containing all properties.
  std::map<std::string, GesturesProp*> properties_;
};

// structure containing the function pointer to property creation
// methods. This structure has to be passed to the gestures library to
// access this property provider.
extern GesturesPropProvider CPropProvider;

}  // namespace replay

#endif  // PROP_PROVIDER_H_
