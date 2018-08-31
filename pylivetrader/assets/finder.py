#
# Copyright 2016 Quantopian, Inc.
# Modifications Copyright 2018 Alpaca
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from pylivetrader.errors import (
    EquitiesNotFound, SidsNotFound, SymbolNotFound, NotSupported
)
from pylivetrader.misc.zipline_utils import split_delimited_symbol


class AssetFinder:

    def __init__(self, backend):
        self.backend = backend

    def clear_cache(self):
        del self.asset_cache

    @property
    def _asset_cache(self):
        if hasattr(self, 'asset_cache'):
            return self.asset_cache

        self.asset_cache = {
            asset.sid: asset
            for asset in self.backend.get_equities()
        }

        return self.asset_cache

    @property
    def symbol_ownership_map(self):
        return {
            split_delimited_symbol(v.symbol): v
            for k, v in self._asset_cache.items()
        }

    @property
    def fuzzy_symbol_ownership_map(self):
        m = {}
        for (cs, scs), v in self.symbol_ownership_map.items():
            m[cs + scs] = v
        return m

    def retrieve_all(self, sids, default_none=False):
        """
        Retrieve all assets in `sids`.

        Parameters
        ----------
        sids : iterable of string
            Assets to retrieve.
        default_none : bool
            If True, return None for failed lookups.
            If False, raise `SidsNotFound`.

        Returns
        -------
        assets : list[Asset or None]
            A list of the same length as `sids` containing Assets (or Nones)
            corresponding to the requested sids.

        Raises
        ------
        SidsNotFound
            When a requested sid is not found and default_none=False.
        """

        failures = set()
        hits = {}
        for sid in sids:
            try:
                hits[sid] = self._asset_cache[sid]
            except KeyError:
                if not default_none:
                    failures.add(sid)
                else:
                    hits[sid] = None

        if len(failures) > 0:
            raise SidsNotFound(sids=list(failures))

        return [hits[sid] for sid in sids]

    def retrieve_asset(self, sid, default_none=False):
        """
        Retrieve the Asset for a given sid.
        """
        try:
            asset = self._asset_cache[sid]
            if asset is None and not default_none:
                raise SidsNotFound(sids=[sid])
            return asset
        except KeyError:
            raise SidsNotFound(sids=[sid])

    def retrieve_equities(self, sids):
        """
        Retrieve Equity objects for a list of sids.

        Users generally shouldn't need to this method (instead, they should
        prefer the more general/friendly `retrieve_assets`), but it has a
        documented interface and tests because it's used upstream.

        Parameters
        ----------
        sids : iterable[string]

        Returns
        -------
        equities : dict[str -> Equity]

        Raises
        ------
        EquitiesNotFound
            When any requested asset isn't found.
        """
        cache = self._asset_cache

        try:
            return {
                k: cache[k]
                for k in sids
            }
        except KeyError:
            raise EquitiesNotFound(sids=sids)

    def retrieve_futures_contracts(self, sids):
        raise NotSupported

    def lookup_symbol(self, symbol, as_of_date=None, fuzzy=False):
        if symbol is None:
            raise TypeError("Cannot lookup asset for symbol of None for "
                            "as of date {}.".format(as_of_date))

        if fuzzy:
            return self._lookup_symbol_fuzzy(symbol, as_of_date)
        return self._lookup_symbol_strict(symbol, as_of_date)

    def _lookup_symbol_strict(self, symbol, as_of_date=None):
        # split the symbol into the components, if there are no
        # company/share class parts then share_class_symbol will be empty
        company_symbol, share_class_symbol = split_delimited_symbol(symbol)
        try:
            return self.symbol_ownership_map[
                company_symbol,
                share_class_symbol,
            ]
        except KeyError:
            # no equity has ever held this symbol
            raise SymbolNotFound(symbol=symbol)

    def _lookup_symbol_fuzzy(self, symbol, as_of_date=None):
        symbol = symbol.upper()
        company_symbol, share_class_symbol = split_delimited_symbol(symbol)
        try:
            return self.fuzzy_symbol_ownership_map[
                company_symbol + share_class_symbol
            ]
        except KeyError:
            # no equity has ever held a symbol matching the fuzzy symbol
            raise SymbolNotFound(symbol=symbol)

    def lookup_symbols(self, symbols, as_of_date=None, fuzzy=False):
        memo = {}
        out = []
        append_output = out.append
        for sym in symbols:
            if sym in memo:
                append_output(memo[sym])
            else:
                equity = memo[sym] = self.lookup_symbol(sym, as_of_date, fuzzy)
                append_output(equity)
        return out

    @property
    def sids(self):
        return [
            sid
            for sid, _ in self._asset_cache.items()
        ]

    @property
    def equities_sids(self):
        return self.sids

    @property
    def futures_sids(self):
        return []

    def lookup_generic(self,
                       asset_convertible_or_iterable,
                       as_of_date):
        raise NotImplementedError

    def map_identifier_index_to_sids(self, index, as_of_date):
        raise NotImplementedError

    def lifetimes(self, dates, include_start_date):
        raise NotImplementedError
