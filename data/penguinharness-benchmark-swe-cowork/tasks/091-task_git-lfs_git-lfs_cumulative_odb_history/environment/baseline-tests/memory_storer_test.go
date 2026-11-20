package odb

import (
	"bytes"
	"encoding/hex"
	"os"
	"io"
	"io/ioutil"
	"strings"
	"testing"

	"github.com/stretchr/testify/assert"
)

func TestMemoryStorerIncludesGivenEntries(t *testing.T) {
	sha := "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
	hex, err := hex.DecodeString(sha)

	assert.Nil(t, err)

	ms := newMemoryStorer(map[string]io.ReadWriter{
		sha: bytes.NewBuffer([]byte{0x1}),
	})

	buf, err := ms.Open(hex)
	assert.Nil(t, err)

	contents, err := ioutil.ReadAll(buf)
	assert.Nil(t, err)
	assert.Equal(t, []byte{0x1}, contents)
}

func TestMemoryStorerAcceptsNilEntries(t *testing.T) {
	ms := newMemoryStorer(nil)

	assert.NotNil(t, ms)
	assert.Equal(t, 0, len(ms.fs))
}

func TestMemoryStorerDoesntOpenMissingEntries(t *testing.T) {
	sha := "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"

	hex, err := hex.DecodeString(sha)
	assert.Nil(t, err)

	store := newMemoryStorer(nil)
	reader, err := store.Open(hex)
	assert.Nil(t, reader)
	assert.True(t, os.IsNotExist(err))
}

func TestMemoryStorerStoresNewEntries(t *testing.T) {
	hex, err := hex.DecodeString("aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa")
	assert.Nil(t, err)

	ms := newMemoryStorer(nil)

	assert.Equal(t, 0, len(ms.fs))

	_, err = ms.Store(hex, strings.NewReader("hello"))
	assert.Nil(t, err)
	assert.Equal(t, 1, len(ms.fs))

	got, err := ms.Open(hex)
	assert.Nil(t, err)

	contents, err := ioutil.ReadAll(got)
	assert.Nil(t, err)
	assert.Equal(t, "hello", string(contents))
}

func TestMemoryStorerPreservesExistingEntries(t *testing.T) {
	objectID, err := hex.DecodeString("aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa")
	assert.Nil(t, err)
	store := newMemoryStorer(nil)
	count, err := store.Store(objectID, strings.NewReader("original"))
	assert.Nil(t, err)
	assert.EqualValues(t, 8, count)
	count, err = store.Store(objectID, strings.NewReader("replacement"))
	assert.Nil(t, err)
	assert.EqualValues(t, 0, count)
	reader, err := store.Open(objectID)
	assert.Nil(t, err)
	if err != nil { return }
	defer reader.Close()
	contents, err := ioutil.ReadAll(reader)
	assert.Nil(t, err)
	assert.Equal(t, "original", string(contents))
}
