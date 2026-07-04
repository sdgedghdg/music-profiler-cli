package qmc

import (
	"errors"

	"go.uber.org/zap"
)

// streamKeyVault removed — the mmkv upstream (unlock-music.dev/mmkv)
// is no longer accessible (403). MMKV-based key derivation is only needed
// for QQ Music macOS legacy databases; all other QMC files derive keys
// from embedded footers and work without mmkv.

func readKeyFromMMKV(file string, logger *zap.Logger) ([]byte, error) {
	return nil, errors.New("mmkv support removed: upstream module unavailable")
}

func readKeyFromMMKVCustom(mid string) ([]byte, error) {
	return nil, errors.New("mmkv support removed: upstream module unavailable")
}

func OpenMMKV(mmkvPath string, key string, logger *zap.Logger) error {
	return errors.New("mmkv support removed: upstream module unavailable")
}
