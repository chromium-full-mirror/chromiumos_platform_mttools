// Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

#include <prop_provider.h>

#include <base/json/json_reader.h>
#include <base/json/json_writer.h>
#include <base/values.h>
#include <sstream>

#include <generic_stream.h>
#include <util.h>

namespace replay {

using base::Value;
using base::JSONReader;

// Implementation of GesturesProp for all numerical types
// Conversion between numerical types is handled implicitly by
// the assignment operator. Conversion to string is handled
// by a lexical_cast.
template<typename Type>
class GesturesPropImpl : public GesturesProp {
public:
  GesturesPropImpl(const char* name, Type* value)
      : name_(name), value_(value) {
  }

  virtual void SetValue(int value) {
    *value_ = value;
  }
  virtual void SetValue(short value) {
    *value_ = value;
  }
  virtual void SetValue(bool value) {
    *value_ = value;
  }
  virtual void SetValue(double value) {
    *value_ = value;
  }
  virtual void GetValue(int* value) {
    *value = *value_;
  }
  virtual void GetValue(short* value) {
    *value = *value_;
  }
  virtual void GetValue(bool* value) {
    *value = *value_;
  }
  virtual void GetValue(double* value) {
    *value = *value_;
  }

  virtual void SetValue(const std::string& value) {
    *value_ = lexical_cast<Type>(value);
  }
  virtual void GetValue(std::string* value) {
    *value = lexical_cast<std::string>(value_);
  }

  virtual std::string GetName() {
    return name_;
  }

private:
  std::string name_;
  Type* value_;
};

// GesturesProp implementation for string properties.
// This requires a local string instance to store the result
// of conversions. All conversions are implemented using
// lexical_casts.
template<>
class GesturesPropImpl<const char*> : public GesturesProp {
public:
  // TODO(denniskempin): numeric to string conversion
  GesturesPropImpl(const char* name, const char** value)
      : name_(name), value_(value) {
  }

  virtual void SetValue(int value) {
    local_ = lexical_cast<std::string>(value);
    *value_ = local_.c_str();
  }
  virtual void SetValue(short value) {
    local_ = lexical_cast<std::string>(value);
    *value_ = local_.c_str();
  }
  virtual void SetValue(bool value) {
    local_ = lexical_cast<std::string>(value);
    *value_ = local_.c_str();
  }
  virtual void SetValue(double value) {
    local_ = lexical_cast<std::string>(value);
    *value_ = local_.c_str();
  }
  virtual void GetValue(int* value) {
    *value = lexical_cast<int>(*value_);
  }
  virtual void GetValue(short* value) {
    *value = lexical_cast<short>(*value_);
  }
  virtual void GetValue(bool* value) {
    *value = lexical_cast<bool>(*value_);
  }
  virtual void GetValue(double* value) {
    *value = lexical_cast<int>(*value_);
  }

  virtual void SetValue(const std::string& value) {
    local_ = value;
    *value_ = local_.c_str();
  }
  virtual void GetValue(std::string* value) {
    *value = *value_;
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

template<typename Type>
GesturesProp* PropProvider::CreateProp(const char* name, Type* loc,
                                       const Type init) {
  *loc = init;
  GesturesProp* prop = new GesturesPropImpl<Type>(name, loc);
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

bool PropProvider::Load(GenericIStream* stream) {
  std::string data((std::istreambuf_iterator<char>(*stream->GetStream())),
                   std::istreambuf_iterator<char>());
  return LoadString(data);
}

bool PropProvider::LoadString(const std::string& data) {
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
    switch (value->GetType()) {
    case Value::TYPE_INTEGER: {
      int intVal;
      value->GetAsInteger(&intVal);
      SetValue<int>(*iter, intVal);
      break;
    }
    case Value::TYPE_BOOLEAN: {
      bool boolVal;
      value->GetAsBoolean(&boolVal);
      SetValue<GesturesPropBool>(*iter, boolVal);
      break;
    }
    case Value::TYPE_DOUBLE: {
      double doubleVal;
      value->GetAsDouble(&doubleVal);
      SetValue<double>(*iter, doubleVal);
      break;
    }
    case Value::TYPE_STRING: {
      std::string stringVal;
      value->GetAsString(&stringVal);
      SetValue<std::string>(*iter, stringVal);
      break;
    }
    default:
      std::cerr << "Invalid property type: " << *iter << std::endl;
      std::cerr << "Expected Integer, Boolean, Double or String" << std::endl;
      return false;
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
                                 const Type init) {
  PropProvider* pp = static_cast<PropProvider*>(data);
  return pp->CreateProp<Type>(name, loc, init);
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
    PropProviderCreate<const char*>,
    PropProviderCreate<double>,
    PropProviderRegisterHandlers,
    PropProviderFree
};

}  // namespace replay

