#!/usr/bin/env python
# Copyright 2022 Google LLC
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.

import argparse
import codecs
import math
import os
import re
import sys
import yaml

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import xngen
import xnncommon

parser = argparse.ArgumentParser(
    description='Generates enum header and convertion-to-string code.')
parser.add_argument(
    '-s',
    '--spec',
    metavar='FILE',
    required=True,
    help='Specification (YAML) file')
parser.add_argument(
    '--output_src',
    metavar='FILE',
    required=True,
    help='Output C source file')
parser.add_argument(
    '--output_hdr',
    metavar='FILE',
    required=True,
    help='Output C/C++ header file')
parser.add_argument(
    '-e',
    '--enum',
    metavar='NAME',
    required=True,
    help='Name of the enum variable')
parser.set_defaults(defines=[])


def generate_source(enum_name, spec_path, output_path, header_path):
  with codecs.open(spec_path, 'r', encoding='utf-8') as spec_file:
    spec_yaml = yaml.safe_load(spec_file)
    if not isinstance(spec_yaml, list):
      raise ValueError('expected a list of enumeration values in the spec')

    output = f"""\
// Copyright 2022 Google LLC
//
// This source code is licensed under the BSD-style license found in the
// LICENSE file in the root directory of this source tree.
//
// Auto-generated file. Do not edit!
//   Specification: {spec_path}
//   Generator: {sys.argv[0]}


#include <assert.h>
#include <stdint.h>

#include <{header_path}>\n\n\n"""

    max_offset = sum(len(entry['string']) + 1 for entry in spec_yaml[:-1])
    if max_offset < 256:
      offset_type = 'uint8_t'
    elif max_offset < 65536:
      offset_type = 'uint16_t'
    else:
      offset_type = 'uint32_t'

    offset_declaration = f'static const {offset_type} offset[{len(spec_yaml)}] = {{\n ';
    string_declaration = 'static const char data[] =\n'
    pos = 0
    for i, spec_entry in enumerate(spec_yaml):
      enum_item_name = spec_entry['name']
      assert enum_item_name.startswith(f"{enum_name}_")
      enum_item_string = spec_entry['string']

      if i + 1 != len(spec_yaml):
        string_declaration += f'  "{enum_item_string}' + '\\0"\n'
        offset_declaration += f' {str(pos)},'
      else:
        string_declaration += f'  "{enum_item_string}' + '";\n'
        offset_declaration += f' {str(pos)}' + '\n};'

      # Wrap offset array on 120 columns
      last_offset_line = offset_declaration[offset_declaration.rfind('\n')+1:]
      if len(last_offset_line) > 120:
        last_offset_start = offset_declaration.rfind(',', 0, -1) + 1
        offset_declaration = offset_declaration[:last_offset_start] + '\n ' + offset_declaration[last_offset_start:]

      pos += len(enum_item_string) + 1

    output += offset_declaration
    output += '\n\n'
    output += string_declaration

    arg_name = enum_name[len("xnn_"):]
    output += f"""
const char* {enum_name}_to_string(enum {enum_name} {arg_name}) {{
  assert({arg_name} >= {spec_yaml[0]['name']});
  assert({arg_name} <= {spec_yaml[-1]['name']});
  return &data[offset[{arg_name}]];
}}\n"""

    txt_changed = True
    if os.path.exists(output_path):
      with codecs.open(output_path, 'r', encoding='utf-8') as output_file:
        txt_changed = output_file.read() != output

    if txt_changed:
      with codecs.open(output_path, 'w', encoding='utf-8') as output_file:
        output_file.write(output)

def generate_header(enum_name, spec_path, output_path):
  with codecs.open(spec_path, 'r', encoding='utf-8') as spec_file:
    spec_yaml = yaml.safe_load(spec_file)
    if not isinstance(spec_yaml, list):
      raise ValueError('expected a list of enumeration values in the spec')

    output = f"""\
// Copyright 2022 Google LLC
//
// This source code is licensed under the BSD-style license found in the
// LICENSE file in the root directory of this source tree.
//
// Auto-generated file. Do not edit!
//   Specification: {spec_path}
//   Generator: {sys.argv[0]}

#pragma once

#include <xnnpack/common.h>


#ifdef __cplusplus
extern "C" {{
#endif

enum {enum_name} {{\n"""

    enum_item_name = spec_yaml[0]['name']
    assert enum_item_name.startswith(f"{enum_name}_")
    output += f'  {enum_item_name}' + ' = 0,\n'
    for spec_entry in spec_yaml[1:]:
      enum_item_name = spec_entry['name']
      assert enum_item_name.startswith(f"{enum_name}_")
      output += f'  {enum_item_name}' + ',\n'

    arg_name = enum_name[len("xnn_"):]
    output += f"""}};

XNN_INTERNAL const char* {enum_name}_to_string(enum {enum_name} {arg_name});

#ifdef __cplusplus
}}  // extern "C"
#endif
"""


    txt_changed = True
    if os.path.exists(output_path):
      with codecs.open(output_path, 'r', encoding='utf-8') as output_file:
        txt_changed = output_file.read() != output

    if txt_changed:
      with codecs.open(output_path, 'w', encoding='utf-8') as output_file:
        output_file.write(output)

def main(args):
  options = parser.parse_args(args)
  generate_header(options.enum, options.spec, options.output_hdr)

  assert options.enum.startswith('xnn_')
  header_path = 'xnnpack/' + options.enum[len('xnn_'):].replace('_', '-') + '.h'
  generate_source(options.enum, options.spec, options.output_src, header_path)

if __name__ == '__main__':
  main(sys.argv[1:])
