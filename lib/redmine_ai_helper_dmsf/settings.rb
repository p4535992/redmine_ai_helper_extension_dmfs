# frozen_string_literal: true
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 p4535992 and contributors.

module RedmineAiHelperDmsf
  # Administrator settings of this extension, stored by Redmine as the
  # serialized plugin setting +plugin_redmine_ai_helper_extension_dmfs+.
  #
  # The fields are rendered inside AI Helper's global settings page, but the
  # values belong to this plugin: they are read and written here only, so AI
  # Helper's own model, migrations and settings are never modified.
  #
  # Every value is normalized to the "0"/"1" strings used by Redmine's
  # checkboxes. A stored hash written by an older release, a missing key or a
  # hand-edited value therefore cannot enable a feature by accident.
  module Settings
    # Key of the DMSF full-text (Xapian) search opt-in.
    FULL_TEXT_SEARCH_KEY = "full_text_search_enabled"
    # Stored value of an enabled flag.
    ENABLED = "1"
    # Stored value of a disabled flag.
    DISABLED = "0"
    # Defaults applied to installations that never saved this plugin's settings.
    DEFAULTS = { FULL_TEXT_SEARCH_KEY => ENABLED }.freeze

    class << self
      # Stored values merged over the defaults, always with string keys.
      # Redmine applies a plugin default only when no row exists, so a stored
      # hash from an older release is merged here instead.
      # @return [Hash{String => String}]
      def values
        merged = DEFAULTS.dup
        stored = Setting.plugin_redmine_ai_helper_extension_dmfs
        return merged unless stored.is_a?(Hash)

        stored.each { |key, value| merged[key.to_s] = value.to_s }
        merged
      end

      # @return [Boolean] whether DMSF's full-text index may be queried
      def full_text_search_enabled?
        values[FULL_TEXT_SEARCH_KEY] == ENABLED
      end

      # Persists submitted values. Only known keys are written, and only "1"
      # enables a flag. A submission without the key keeps the stored value, so
      # a request that does not carry this form cannot reset it.
      # @param submitted [Hash, ActionController::Parameters, nil] extension fields
      # @return [Hash{String => String}] the stored values after the update
      def update(submitted)
        updated = values
        return updated unless submitted.respond_to?(:key?) && submitted.key?(FULL_TEXT_SEARCH_KEY)

        updated[FULL_TEXT_SEARCH_KEY] = submitted[FULL_TEXT_SEARCH_KEY].to_s == ENABLED ? ENABLED : DISABLED
        Setting.plugin_redmine_ai_helper_extension_dmfs = updated
        updated
      end
    end
  end
end
