// Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

#include "prop_provider.h"

#include <iostream>

#include <base/json/json_reader.h>
#include <base/json/json_writer.h>
#include <base/values.h>

#include "util.h"

namespace replay {

using base::Value;
using base::JSONReader;

// Implementation of GesturesProp for all numerical types
template<typename Type>
class GesturesPropImpl : public GesturesProp {
 public:
  GesturesPropImpl(const char* name, Type* value)
      : name_(name), value_(value) {
  }

  virtual void SetValue(const std::string& value) {
    *value_ = replay_lexical_cast<Type>(value);
  }

  virtual std::string GetName() {
    return name_;
  }

 private:
  std::string name_;
  Type* value_;
};

// GesturesProp implementation for string properties.
// This requires a local string instance to store a copy of the value.
template<>
class GesturesPropImpl<const char*> : public GesturesProp {
 public:
  GesturesPropImpl(const char* name, const char** value)
      : name_(name), value_(value) {
  }

  virtual void SetValue(const std::string& value) {
    local_ = value;
    *value_ = local_.c_str();
  }

  virtual std::string GetName() {
    return name_;
  }

 private:
  std::string name_;
  const char** value_;
  std::string local_;
};

PropProvider::PropProvider() {
}

PropProvider::~PropProvider() {
  typedef std::map<std::string, GesturesProp*>::iterator iter_t;
  for (iter_t iter = properties_.begin(); iter != properties_.end(); ++iter) {
    delete iter->second;
  }
  properties_.clear();
}

bool PropProvider::CheckIntegrity() {
  if (properties_cache_.size() > 0) {
    typedef std::map<std::string, std::string>::iterator iter_t;
    for (iter_t iter = properties_cache_.begin();
         iter != properties_cache_.end(); ++iter) {
      std::cerr << "Unknown Property: " << iter->first << std::endl;
    }
    return false;
  }
  return true;
}

template<typename Type>
GesturesProp* PropProvider::CreateProp(const char* name, Type* loc,
                                       size_t count, const Type* init) {
  GesturesProp* prop = new GesturesPropImpl<Type>(name, loc);
  if (properties_cache_.find(name) != properties_cache_.end()) {
    prop->SetValue(properties_cache_[name]);
    properties_cache_.erase(name);
  } else {
    for (size_t i = 0; i < count; i++)
      loc[i] = init[i];
  }
  properties_[std::string(name)] = prop;
  return prop;
}

GesturesProp* PropProvider::GetPropSafe(const std::string& name) {
  GesturesProp* prop = properties_[name];
  if (!prop) {
    std::cerr << "Property " << name << " does not exist." << std::endl;
    exit(-1);
  }
  return prop;
}

bool PropProvider::Load(const std::string& data) {
  int error_code;
  std::string error_msg;
  Value* root = JSONReader::ReadAndReturnError(data, true, &error_code,
                                               &error_msg);
  if (!root) {
    std::cerr << "Parse failed: " << error_msg << std::endl;
    return false;
  }

  if (root->GetType() != Value::TYPE_DICTIONARY) {
    std::cerr << "Root object has to be a dictionary" << std::endl;
    return false;
  }

  DictionaryValue* dict = static_cast<DictionaryValue*>(root);

  typedef DictionaryValue::key_iterator iter_t;
  for (iter_t iter = dict->begin_keys(); iter != dict->end_keys(); ++iter) {
    Value* value;

    dict->GetWithoutPathExpansion(*iter, &value);
    std::string stringVal;
    switch (value->GetType()) {
    case Value::TYPE_INTEGER: {
      int intVal;
      value->GetAsInteger(&intVal);
      stringVal = replay_lexical_cast<std::string>(intVal);
      break;
    }
    case Value::TYPE_BOOLEAN: {
      bool boolVal;
      value->GetAsBoolean(&boolVal);
      stringVal = replay_lexical_cast<std::string>(boolVal);
      break;
    }
    case Value::TYPE_DOUBLE: {
      double doubleVal;
      value->GetAsDouble(&doubleVal);
      stringVal = replay_lexical_cast<std::string>(doubleVal);
      break;
    }
    case Value::TYPE_STRING: {
      value->GetAsString(&stringVal);
      break;
    }
    default:
      std::cerr << "Invalid property type: " << *iter << std::endl;
      std::cerr << "Expected Integer, Boolean, Double or String" << std::endl;
      return false;
    }

    if (properties_.find(*iter) == properties_.end()) {
      properties_cache_[*iter] = stringVal;
    } else {
      GetPropSafe(*iter)->SetValue(stringVal);
    }
  }
  return true;
}

void PropProvider::Free(GesturesProp* prop) {
  properties_.erase(prop->GetName());
}

// Wrapper method to create properties for the gestures library.
template<typename Type>
GesturesProp* PropProviderCreate(void* data, const char* name, Type* loc,
                                 size_t count, const Type* init) {
  PropProvider* pp = static_cast<PropProvider*>(data);
  return pp->CreateProp<Type>(name, loc, count, init);
}

GesturesProp* PropProviderCreateString(void* data, const char* name,
                                       const char** loc,
                                       const char* const init) {
  PropProvider* pp = static_cast<PropProvider*>(data);
  return pp->CreateProp<const char*>(name, loc, static_cast<size_t>(1), &init);
}

// Dummy method. This provider does not support Get/Set handlers.
void PropProviderRegisterHandlers(void* data, GesturesProp* prop,
                                  void* handler_data,
                                  GesturesPropGetHandler getter,
                                  GesturesPropSetHandler setter) {
}

// Wrapper method to free properties for the gestures library.
void PropProviderFree(void* data, GesturesProp* prop) {
  PropProvider* pp = static_cast<PropProvider*>(data);
  return pp->Free(prop);
}

GesturesPropProvider CPropProvider = {
    PropProviderCreate<int>,
    PropProviderCreate<short>,
    PropProviderCreate<GesturesPropBool>,
    PropProviderCreateString,
    PropProviderCreate<double>,
    PropProviderRegisterHandlers,
    PropProviderFree
};

}  // namespace replay

