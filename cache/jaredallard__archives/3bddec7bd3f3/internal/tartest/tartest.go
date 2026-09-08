// Copyright (C) 2024 archives contributors
//
// This program is free software: you can redistribute it and/or modify
// it under the terms of the GNU Lesser General Public License as
// published by the Free Software Foundation, either version 3 of the
// License, or (at your option) any later version.
//
// This program is distributed in the hope that it will be useful,
// but WITHOUT ANY WARRANTY; without even the implied warranty of
// MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
// GNU Lesser General Public License for more details.
//
// You should have received a copy of the GNU Lesser General Public
// License along with this program. If not, see
// <https://www.gnu.org/licenses/>.
//
// SPDX-License-Identifier: LGPL-3.0

// Package tartest contains helpers for creating tar archives for usage
// in tests in the archives package.
package tartest

import (
	"archive/tar"
	"bytes"
	"compress/gzip"
	"fmt"
	"io"

	"github.com/klauspost/compress/zstd"
	xznocgo "github.com/ulikunitz/xz"
)

// Container represents the container of a tar file.
type Container int

const (
	// ContainerNone denotes no container. This is the default.
	ContainerNone Container = iota
	// ContainerGz is a tar archive compressed with gzip.
	ContainerGz
	// ContainerXz is a tar archive compressed with xz.
	ContainerXz
	// ContainerBz2 is a tar archive compressed with bzip2.
	ContainerBz2
	// ContainerZstd is a tar archive compressed with zstd.
	ContainerZstd
)

// Options is a struct for interacting with containers.
type Options struct {
	Container Container
}

// OptionFn modifies a [Options] struct.
type OptionFn func(*Options)

// WithContainer denotes that a specific container should be used when
// creating the tar archive.
func WithContainer(c Container) OptionFn {
	return func(o *Options) {
		o.Container = c
	}
}

// Create creates a new tar archive with a single file, file.txt,
// containing the contents "hello world".
func Create(options ...OptionFn) (io.Reader, error) {
	opts := &Options{Container: ContainerNone}
	for _, o := range options {
		o(opts)
	}

	buf := new(bytes.Buffer)

	var container io.WriteCloser
	switch opts.Container { //nolint:exhaustive // Why: None is zero value.
	case ContainerGz:
		container = gzip.NewWriter(buf)
	case ContainerXz:
		var err error
		container, err = xznocgo.NewWriter(buf)
		if err != nil {
			return nil, fmt.Errorf("failed to create xz writer: %w", err)
		}
	case ContainerBz2:
		var err error
		container, err = newBzip2Writer(buf)
		if err != nil {
			return nil, fmt.Errorf("failed to create bzip2 writer: %w", err)
		}
	case ContainerZstd:
		var err error
		container, err = zstd.NewWriter(buf)
		if err != nil {
			return nil, fmt.Errorf("failed to create zstd writer: %w", err)
		}
	}

	var tw *tar.Writer
	if container == nil {
		tw = tar.NewWriter(buf)
	} else {
		tw = tar.NewWriter(container)
		defer container.Close() //nolint:errcheck // Why: Best effort
	}

	contents := []byte("hello world")
	if err := tw.WriteHeader(&tar.Header{
		Name: "file.txt",
		Size: int64(len(contents)),
		Mode: 0o644,
	}); err != nil {
		return nil, fmt.Errorf("failed to write header: %w", err)
	}

	_, err := tw.Write(contents)
	if err != nil {
		return nil, fmt.Errorf("failed to write contents: %w", err)
	}

	if err := tw.Close(); err != nil {
		return nil, fmt.Errorf("failed to close tar writer: %w", err)
	}

	return buf, nil
}
