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

package archives

import (
	"errors"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"strings"
)

// sanitizeArchivePath sanitizes the provided archive file pathing from
// "G305: Zip Slip vulnerability".
//
// See: https://github.com/securego/gosec/issues/324
func sanitizeArchivePath(d, t string) (v string, err error) {
	v = filepath.Join(d, t)
	if strings.HasPrefix(v, filepath.Clean(d)) {
		return v, nil
	}

	return "", fmt.Errorf("%s: %s", "content filepath is tainted", t)
}

// extract contains low level logic for extracting archives.
func extract(a Archive, dest string, opts *ExtractOptions) error {
	for {
		h, err := a.Next()
		if err != nil {
			if errors.Is(err, io.EOF) {
				break
			}

			return fmt.Errorf("failed to read archive header: %w", err)
		}

		path, err := sanitizeArchivePath(dest, h.Name)
		if err != nil {
			return err
		}

		switch h.Type {
		case HeaderDir:
			//nolint:gosec // Why: acceptable, we're a tar extractor.
			if err := os.MkdirAll(path, h.Mode); err != nil {
				return fmt.Errorf("failed to create directory: %w", err)
			}
		case HeaderFile:
			// Sometimes the directory entry is missing, so we need to create
			// it.
			//
			//nolint:gosec // Why: acceptable, we're a tar extractor.
			if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
				return fmt.Errorf("failed to create directory: %w", err)
			}

			//nolint:gosec // Why: acceptable, we're a tar extractor.
			f, err := os.Create(path)
			if err != nil {
				return fmt.Errorf("failed to create file: %w", err)
			}

			if _, err := io.Copy(f, a); err != nil {
				_ = f.Close() //nolint:errcheck // Why: Best effort to close the file.
				return fmt.Errorf("failed to copy file contents: %w", err)
			}

			if err := f.Close(); err != nil {
				return fmt.Errorf("failed to close file: %w", err)
			}
		default:
			return fmt.Errorf("unsupported file type in package (%s: %v)", h.Name, h.Type)
		}

		if opts.PreservePermissions != nil && *opts.PreservePermissions {
			if err := os.Chmod(path, h.Mode); err != nil {
				return fmt.Errorf("failed to set file permissions: %w", err)
			}
		}

		if opts.PreserveOwnership {
			if err := os.Chown(path, h.UID, h.GID); err != nil {
				return fmt.Errorf("failed to set file ownership: %w", err)
			}
		}

		if err := os.Chtimes(path, h.AccessTime, h.ModTime); err != nil {
			return fmt.Errorf("failed to set file times: %w", err)
		}
	}

	return nil
}
