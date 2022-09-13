// Copyright 2012 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

#ifndef PROP_PROVIDER_H_
#define PROP_PROVIDER_H_

#include <map>
#include <string>

#include <gestures/gestures.h>

#include "util.h"

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

template<typename Out, typename In>
Out replay_lexical_cast(const In& in) {
  return lexical_cast<Out>(in);
}
template<>
inline GesturesPropBool replay_lexical_cast<GesturesPropBool, std::string>(
    const std::string& in) {
  return lexical_cast<int>(in);
}

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
  GesturesProp* CreateProp(const char* name, Type* loc, size_t count,
                           const Type* init);

  // Read a property.
  // The value parameter will store the property value, and will not be
  // modified if the property does not exist.
  template<typename Type>
  void GetPropValue(const char* name, Type* value) {
    if (properties_cache_.find(name) != properties_cache_.end()) {
      *value = replay_lexical_cast<Type>(properties_cache_[name]);
      properties_cache_.erase(name);
    }
  }

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
