# -*- coding: utf-8 -*-
#
# Copyright 2022 Nitrokey Developers
#
# Licensed under the Apache License, Version 2.0, <LICENSE-APACHE or
# http://apache.org/licenses/LICENSE-2.0> or the MIT license <LICENSE-MIT or
# http://opensource.org/licenses/MIT>, at your option. This file may not be
# copied, modified, or distributed except according to those terms.

from typing import Any, Mapping, Sequence, Union

CborType = Union[int, bool, str, bytes, Sequence[Any], Mapping[Any, Any]]

def dump_dict(data: Mapping[CborType, CborType]) -> bytes: ...
