package config

import (
	"github.com/alecthomas/kingpin"
	"github.com/go-playground/validator/v10"
	"genai-observability/stackstate"
	"genai-observability/stackstate/receiver"
	"github.com/spf13/viper"
	"log/slog"
	"os"
	"path"
	"path/filepath"
	"strings"
)

type Configuration struct {
	StackState stackstate.StackState `mapstructure:"stackstate" validate:"required"`
	Instance   receiver.Instance     `mapstructure:"instance" validate:"required"`
	Kubernetes Kubernetes            `mapstructure:"kubernetes" validate:"required"`
}

type Kubernetes struct {
	Cluster           string `mapstructure:"cluster" validate:"required"`
	QueryTimeInterval string `mapstructure:"queryTimeInterval" validate:"required"`
}

func GetConfig() (*Configuration, error) {
	configFile := os.Getenv("CONFIG_FILE")
	if configFile == "" {
		cf := kingpin.Flag("config-file", "config file").Short('c').ExistingFile()
		if *cf != "" {
			configFile = *cf
		}
	}
	c := &Configuration{Instance: receiver.Instance{}}
	v := viper.New()
	v.SetDefault("kubernetes.cluster", "")
	v.SetDefault("kubernetes.queryTimeInterval", "1h")
	v.SetDefault("stackstate.api_url", "")
	v.SetDefault("stackstate.api_key", "")
	v.SetDefault("stackstate.api_token", "")
	v.SetDefault("stackstate.legacy_api", false)
	v.SetDefault("instance.type", "openlit")
	v.SetDefault("instance.url", "local")

	v.SetEnvKeyReplacer(strings.NewReplacer(".", "_"))
	v.AutomaticEnv()
	if configFile != "" {
		d, f := path.Split(configFile)
		if d == "" {
			d = "."
		}
		v.SetConfigName(f[0 : len(f)-len(filepath.Ext(f))])
		v.AddConfigPath(d)
		err := v.ReadInConfig()
		if err != nil {
			slog.Error("Error when reading config file.", slog.Any("error", err))
		}
	}

	if err := v.Unmarshal(c); err != nil {
		slog.Error("Error unmarshalling config", slog.Any("err", err))
		return nil, err
	}

	validate := validator.New(validator.WithRequiredStructEnabled())
	err := validate.Struct(c)
	if err != nil {
		return nil, err
	}
	return c, nil
}
