package testutil

import (
	"os"
	"path/filepath"
	"sync"
)

var (
	rootOnce sync.Once
	rootDir  string
)

// StackPackRoot returns the absolute path to stackpack/suse-ai/.
func StackPackRoot() string {
	rootOnce.Do(func() {
		dir, err := os.Getwd()
		if err != nil {
			panic("cannot get working directory: " + err.Error())
		}
		for {
			candidate := filepath.Join(dir, "stackpack", "suse-ai", "stackpack.conf")
			if _, err := os.Stat(candidate); err == nil {
				rootDir = filepath.Join(dir, "stackpack", "suse-ai")
				return
			}
			parent := filepath.Dir(dir)
			if parent == dir {
				panic("cannot find stackpack/suse-ai/stackpack.conf in any parent directory")
			}
			dir = parent
		}
	})
	return rootDir
}

// ProvisioningDir returns the path to stackpack/suse-ai/provisioning/.
func ProvisioningDir() string {
	return filepath.Join(StackPackRoot(), "provisioning")
}

// TemplatesDir returns the path to stackpack/suse-ai/provisioning/templates/.
func TemplatesDir() string {
	return filepath.Join(ProvisioningDir(), "templates")
}

// ResourcesDir returns the path to stackpack/suse-ai/resources/.
func ResourcesDir() string {
	return filepath.Join(StackPackRoot(), "resources")
}
