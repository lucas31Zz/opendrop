// String tables, transcribed VERBATIM from the pre-1.0 Avalonia app's
// Strings.fr.axaml and Strings.en.axaml. The active language is the engine's `lang` (config),
// exactly like the desktop app's Lang.T lookup.

export type Lang = "fr" | "en";

export const STRINGS = {
  fr: {
    // Main window
    "Status.Starting": "Démarrage...",
    "Status.Running": "Serveur actif",
    "Status.Stopped": "Serveur arrêté",
    "Status.Error": "Erreur",
    "Btn.StartServer": "Démarrer le serveur",
    "Btn.StopServer": "Arrêter le serveur",
    "Btn.Settings": "Paramètres",
    "Btn.Save": "Enregistrer",
    "Btn.Saved": "Enregistré !",
    "Btn.Reset": "Réinitialiser",
    "Btn.Copy": "Copier",
    "Btn.Copied": "Copié ✓",
    "Btn.Discord": "Rejoindre le Discord d'OpenDrop",
    "Btn.Theme": "Changer de thème",
    "Win.Minimize": "Réduire",
    "Win.Maximize": "Agrandir",
    "Win.Restore": "Restaurer",
    "Win.Close": "Fermer",
    "Label.ServerAddress": "ADRESSE DU SERVEUR",
    "Label.QrCode": "QR CODE",
    "Qr.HintStart": "Démarrez le serveur pour générer le QR code",
    "Qr.Unavailable": "QR code indisponible",
    "Qr.Generating": "Génération d'un nouveau token...",
    "Qr.Restarting": "Redémarrage du serveur...",
    "Label.SessionCode": "CODE DE SESSION",
    "Session.Hint": "À saisir sur l'autre appareil quand la session est verrouillée.",
    "Label.TokenRefresh": "RAFRAÎCHISSEMENT DU TOKEN",
    "Token.Never": "Jamais",
    "Token.5m": "5 minutes",
    "Token.15m": "15 minutes",
    "Token.30m": "30 minutes",
    "Token.1h": "1 heure",
    "Token.NextRefresh": "Prochain rafraîchissement dans",
    "Label.Folders": "DOSSIERS",
    "Folders.Received": "Reçus :",
    "Folders.Shared": "Partagés :",
    "Folders.Missing": "Ce dossier n'existe pas : {0}",
    "Label.ReceiveQuota": "QUOTA DE RÉCEPTION",
    "Quota.Analyzing": "Analyse...",
    "Quota.Description": "Dossier de réception actuel, mis à jour automatiquement.",
    "Quota.Usage": "Actuellement reçu : {0} dans ce dossier",
    "Quota.NoFiles": "Aucun fichier reçu dans ce dossier pour l'instant",
    "Quota.Scanning": "Analyse du dossier...",
    "Quota.Unlimited": "{0} reçus (illimité)",
    "Quota.UsageInFolder": "{0} reçus dans ce dossier",
    "Err.CannotStart": "Impossible de démarrer le serveur.",
    "Err.CannotRestart": "Impossible de redémarrer le serveur.",
    "Err.CannotStop": "Impossible d'arrêter le serveur.",
    "Err.OpenBrowser": "Impossible d'ouvrir le navigateur.",
    "Err.Settings": "Erreur Paramètres :",
    "Err.Prefix": "Erreur :",

    // Settings window
    "Settings.Title": "Paramètres OpenDrop",
    "Settings.Header": "Paramètres",
    "Section.General": "GÉNÉRAL",
    "Section.Storage": "STOCKAGE",
    "Section.Security": "SÉCURITÉ",
    "Section.Network": "RÉSEAU",
    "Tab.General": "Général",
    "Tab.Storage": "Stockage",
    "Tab.Security": "Sécurité",
    "Tab.Network": "Réseau",
    "Tab.Devices": "Appareils",
    "Tab.Appearance": "Apparence",
    "Tab.Updates": "Mises à jour",

    // Device pairing
    "Devices.Token": "Jeton d'appareil",
    "Devices.PourParrainer": "Pour parrainer :",
    "Devices.OpenBrowser": "Ouvrir dans le navigateur",
    "Devices.Reset": "Réinitialiser",
    "Devices.ResetConfirm":
      "Réinitialiser cassera le parrainage de tous les appareils appairés : ils devront être appairés à nouveau. Continuer ?",
    "Devices.Stopped": "Le serveur est arrêté.",
    "Devices.None": "Aucun appareil associé.",
    "Devices.Dissociate": "Dissocier",
    "Devices.DissociateConfirm": "Retirer cet appareil ?",
    "Field.Language": "Langue",
    "Field.ReceiveFolder": "Dossier de réception",
    "Field.ShareFolder": "Dossier de partage",
    "Field.Port": "Port",
    "Field.GlobalQuota": "Quota global du dossier de réception",
    "Quota.UnitHint": "Go ou Mo",
    "Quota.NoUnitHint":
      "Sans unité = Go : 500 vaut 500 Go, 500 mo vaut 500 Mo. 0 = illimité.",
    "Quota.CumulativeHint":
      "Taille cumulée des fichiers reçus : un envoi qui ferait dépasser le quota est refusé.",
    "Field.NewToken": "Nouveau token au démarrage",
    "Field.NetworkInterface": "Interface réseau",
    "Interface.Auto": "Détection automatique",
    "Browse.ReceiveTitle": "Choisir le dossier de réception",
    "Browse.ShareTitle": "Choisir le dossier de partage",
    "Quota.Invalid":
      'Quota invalide : "{0}"\n\nExemples acceptés : 0,5 go (512 mo), 500 mo, 10.75.\nUn nombre sans unité est compté en Go. 0 = illimité.',
    "Quota.BigTitle": "Quota global important",
    "Quota.BigBody":
      "Quota global de {0}\n\nCe quota dépasse 20 % de l'espace libre sur ce disque ({1} libres).\n\nDes transferts successifs finiraient par saturer ce disque : la machine peut ralentir, voire ne plus pouvoir écrire (système, mises à jour, fichiers temporaires).\n\nÀ vos risques et périls : enregistrer quand même ?",

    // Message boxes
    "Msg.Yes": "Oui",
    "Msg.No": "Non",
    "Msg.Ok": "OK",
    "Msg.Cancel": "Annuler",

    // Shared files
    "Label.SharedFiles": "FICHIERS PARTAGÉS",
    "Label.DropFilesHere": "déposez des fichiers ici",
    "Btn.AddFiles": "Ajouter des fichiers...",
    "Btn.Rename": "Renommer",
    "Btn.Delete": "Supprimer",
    "Btn.Refresh": "Actualiser",
    "Btn.Open": "Ouvrir",
    "Btn.PutBack": "Remettre",
    "Files.Empty": "Le dossier de partage est vide.",
    "Files.MissingFolder":
      "Le dossier de partage n'existe pas. Choisissez-en un dans les Paramètres.",
    "Files.SelectOne": "Sélectionnez exactement un fichier.",
    "Files.SelectAny": "Sélectionnez au moins un fichier.",
    "Files.SelectAll": "Tout sélectionner",
    "Files.RenameTitle": "Renommer",
    "Files.RenamePrompt": "Nouveau nom :",
    "Files.RenameInvalid": "Ce nom ne peut pas être utilisé sur ce système.",
    "Files.RenameExists": "Un fichier porte déjà ce nom.",
    "Files.RenameBatchPrompt":
      "Nouveau nom de base pour les {0} fichiers sélectionnés.\n\nIls sont numérotés dans l'ordre : nom, nom (2), nom (3)... Chaque fichier conserve sa propre extension.",
    "Files.RenameBatchFailed": "{0} fichier(s) n'ont pas pu être renommés.",
    "Files.DeleteTitle": "Suppression",
    "Files.DeleteConfirm": "Supprimer {0} fichier(s) ?\n\n{1}\n\nLes fichiers sont retirés du disque.",
    "Files.DeleteFailed": "{0} fichier(s) n'ont pas pu être supprimés.",
    "Files.AddTitle": "Ajouter des fichiers au dossier de partage",
    "Files.CopyOrMove":
      "Les copier dans le dossier de partage, ou les y déplacer ?\n\nDéplacer retire l'original de son dossier actuel.",
    "Files.Copy": "Copier",
    "Files.Move": "Déplacer",
    "Files.Adding": "Ajout des fichiers...",
    "Files.AddFailed": "{0} ajouté(s), {1} en échec.",
    "Files.AddSkipped": "{0} ajouté(s), {1} déjà dans le dossier de partage.",
    "Files.NotFound": "Ce fichier n'est plus dans le dossier de partage.",
    "Files.PutBackTitle": "Remettre",
    "Files.PutBackConfirm": "Remettre {0} dans son dossier d'origine ?\n\n{1}",

    // Appearance
    "Section.Appearance": "APPARENCE",
    "Field.Theme": "Thème",
    "Theme.Light": "Clair",
    "Theme.Dark": "Sombre",

    // Updates
    "Section.Updates": "MISES À JOUR",
    "Field.Version": "Version",
    "Btn.CheckUpdates": "Vérifier les mises à jour",
    "Update.Title": "Mises à jour",
    "Up.Checking": "Vérification des mises à jour...",
    "Up.UpToDate": "OpenDrop est à jour ({0}).",
    "Up.Available":
      "Une nouvelle version d'OpenDrop est disponible : {0} (vous avez {1}).",
    "Up.Error": "Impossible de vérifier les mises à jour : {0}",
    "Up.DialogTitle": "Mise à jour disponible",
    "Up.DialogBody":
      "Une nouvelle version d'OpenDrop est disponible : {0} (vous avez {1}).\n\nLa télécharger et l'installer maintenant ?",
    "Up.ToastTitle": "Nouvelle version disponible",
    "Up.Downloading": "Téléchargement de l'installateur...",
    "Up.Launching": "Lancement de l'installateur (validation administrateur)...",
    "Up.DownloadError": "Échec du téléchargement : {0}",
    "Up.InstallError": "Impossible de lancer l'installateur : {0}",
    "Btn.UpdateNow": "Mettre à jour",
    "Btn.Later": "Plus tard",
    "Btn.Refuse": "Refuser",

    // Port conflict (NEW: the desktop app has no such card)
    "Status.PortBusy": "Port {0} occupé",
    "Port.UsedBy": "{0} (PID {1}) utilise ce port.",
    "Btn.KillAndStart": "Tuer {0} et démarrer",
    "Port.KillTitle": "Tuer l'application ?",
    "Port.KillBody":
      "{0} (PID {1}) utilise le port {2}.\n\nLe tuer pour libérer le port et démarrer le serveur ?\n\nToute donnée non enregistrée dans cette application sera perdue.",
    "Port.KillFailed": "Le port {0} est toujours occupé.",
    // System tray context menu (native, built in Rust via set_tray_labels).
    "Tray.Show": "Afficher OpenDrop",
    "Tray.Quit": "Quitter OpenDrop",
  },
  en: {
    // Main window
    "Status.Starting": "Starting...",
    "Status.Running": "Server running",
    "Status.Stopped": "Server stopped",
    "Status.Error": "Error",
    "Btn.StartServer": "Start server",
    "Btn.StopServer": "Stop server",
    "Btn.Settings": "Settings",
    "Btn.Save": "Save",
    "Btn.Saved": "Saved!",
    "Btn.Reset": "Reset",
    "Btn.Copy": "Copy",
    "Btn.Copied": "Copied ✓",
    "Btn.Discord": "Join the OpenDrop Discord",
    "Btn.Theme": "Switch theme",
    "Win.Minimize": "Minimize",
    "Win.Maximize": "Maximize",
    "Win.Restore": "Restore",
    "Win.Close": "Close",
    "Label.ServerAddress": "SERVER ADDRESS",
    "Label.QrCode": "QR CODE",
    "Qr.HintStart": "Start the server to generate the QR code",
    "Qr.Unavailable": "QR code unavailable",
    "Qr.Generating": "Generating a new token...",
    "Qr.Restarting": "Restarting the server...",
    "Label.SessionCode": "SESSION CODE",
    "Session.Hint": "Type it on the other device when the session is locked.",
    "Label.TokenRefresh": "TOKEN REFRESH",
    "Token.Never": "Never",
    "Token.5m": "5 minutes",
    "Token.15m": "15 minutes",
    "Token.30m": "30 minutes",
    "Token.1h": "1 hour",
    "Token.NextRefresh": "Next refresh in",
    "Label.Folders": "FOLDERS",
    "Folders.Received": "Received:",
    "Folders.Shared": "Shared:",
    "Folders.Missing": "This folder does not exist: {0}",
    "Label.ReceiveQuota": "RECEIVE QUOTA",
    "Quota.Analyzing": "Analyzing...",
    "Quota.Description": "Current receive folder, updated automatically.",
    "Quota.Usage": "Received so far: {0} in this folder",
    "Quota.NoFiles": "No files received in this folder yet",
    "Quota.Scanning": "Analyzing folder...",
    "Quota.Unlimited": "{0} received (unlimited)",
    "Quota.UsageInFolder": "{0} received in this folder",
    "Err.CannotStart": "Could not start the server.",
    "Err.CannotRestart": "Could not restart the server.",
    "Err.CannotStop": "Could not stop the server.",
    "Err.OpenBrowser": "Could not open the browser.",
    "Err.Settings": "Settings error:",
    "Err.Prefix": "Error:",

    // Settings window
    "Settings.Title": "OpenDrop Settings",
    "Settings.Header": "Settings",
    "Section.General": "GENERAL",
    "Section.Storage": "STORAGE",
    "Section.Security": "SECURITY",
    "Section.Network": "NETWORK",
    "Tab.General": "General",
    "Tab.Storage": "Storage",
    "Tab.Security": "Security",
    "Tab.Network": "Network",
    "Tab.Devices": "Devices",
    "Tab.Appearance": "Appearance",
    "Tab.Updates": "Updates",

    // Device pairing
    "Devices.Token": "Device token",
    "Devices.PourParrainer": "To pair a device:",
    "Devices.OpenBrowser": "Open in browser",
    "Devices.Reset": "Reset",
    "Devices.ResetConfirm":
      "Reset will break pairing for all registered devices: they will have to be paired again. Continue?",
    "Devices.Stopped": "The server is stopped.",
    "Devices.None": "No paired devices.",
    "Devices.Dissociate": "Disconnect",
    "Devices.DissociateConfirm": "Remove this device?",
    "Field.Language": "Language",
    "Field.ReceiveFolder": "Receive folder",
    "Field.ShareFolder": "Share folder",
    "Field.Port": "Port",
    "Field.GlobalQuota": "Global receive-folder quota",
    "Quota.UnitHint": "GB or MB",
    "Quota.NoUnitHint":
      "No unit = GB: 500 means 500 GB, 500 mb means 500 MB. 0 = unlimited.",
    "Quota.CumulativeHint":
      "Total size of received files: an upload that would exceed the quota is rejected.",
    "Field.NewToken": "New token on start",
    "Field.NetworkInterface": "Network interface",
    "Interface.Auto": "Automatic detection",
    "Browse.ReceiveTitle": "Choose the receive folder",
    "Browse.ShareTitle": "Choose the share folder",
    "Quota.Invalid":
      'Invalid quota: "{0}"\n\nAccepted examples: 0.5 gb (512 mb), 500 mb, 10.75.\nA number without a unit is read as GB. 0 = unlimited.',
    "Quota.BigTitle": "Large global quota",
    "Quota.BigBody":
      "Global quota of {0}\n\nThis quota exceeds 20% of the free space on this disk ({1} free).\n\nSuccessive transfers would eventually fill this disk: the machine may slow down and may even be unable to write (system, updates, temporary files).\n\nProceed at your own risk: save anyway?",

    // Message boxes
    "Msg.Yes": "Yes",
    "Msg.No": "No",
    "Msg.Ok": "OK",
    "Msg.Cancel": "Cancel",

    // Shared files
    "Label.SharedFiles": "SHARED FILES",
    "Label.DropFilesHere": "drop files here",
    "Btn.AddFiles": "Add files...",
    "Btn.Rename": "Rename",
    "Btn.Delete": "Delete",
    "Btn.Refresh": "Refresh",
    "Btn.Open": "Open",
    "Btn.PutBack": "Put back",
    "Files.Empty": "The share folder is empty.",
    "Files.MissingFolder":
      "The share folder does not exist. Pick one in Settings.",
    "Files.SelectOne": "Select exactly one file.",
    "Files.SelectAny": "Select at least one file.",
    "Files.SelectAll": "Select all",
    "Files.RenameTitle": "Rename",
    "Files.RenamePrompt": "New name:",
    "Files.RenameInvalid": "That name cannot be used on this system.",
    "Files.RenameExists": "A file with that name already exists.",
    "Files.RenameBatchPrompt":
      "New base name for the {0} selected files.\n\nThey are numbered in order: name, name (2), name (3)... Each file keeps its own extension.",
    "Files.RenameBatchFailed": "{0} file(s) could not be renamed.",
    "Files.DeleteTitle": "Delete",
    "Files.DeleteConfirm":
      "Delete {0} file(s)?\n\n{1}\n\nThe files are removed from the disk.",
    "Files.DeleteFailed": "{0} file(s) could not be deleted.",
    "Files.AddTitle": "Add files to the share folder",
    "Files.CopyOrMove":
      "Copy them into the share folder, or move them there?\n\nMove removes the original from its current folder.",
    "Files.Copy": "Copy",
    "Files.Move": "Move",
    "Files.Adding": "Adding files...",
    "Files.AddFailed": "{0} added, {1} failed.",
    "Files.AddSkipped": "{0} added, {1} already in the share folder.",
    "Files.NotFound": "This file is no longer in the share folder.",
    "Files.PutBackTitle": "Put back",
    "Files.PutBackConfirm": "Move {0} back to its original folder?\n\n{1}",

    // Appearance
    "Section.Appearance": "APPEARANCE",
    "Field.Theme": "Theme",
    "Theme.Light": "Light",
    "Theme.Dark": "Dark",

    // Updates
    "Section.Updates": "UPDATES",
    "Field.Version": "Version",
    "Btn.CheckUpdates": "Check for updates",
    "Update.Title": "Updates",
    "Up.Checking": "Checking for updates...",
    "Up.UpToDate": "OpenDrop is up to date ({0}).",
    "Up.Available":
      "A new version of OpenDrop is available: {0} (you are running {1}).",
    "Up.Error": "Could not check for updates: {0}",
    "Up.DialogTitle": "Update available",
    "Up.DialogBody":
      "A new version of OpenDrop is available: {0} (you are running {1}).\n\nDownload and install it now?",
    "Up.ToastTitle": "New version available",
    "Up.Downloading": "Downloading the installer...",
    "Up.Launching": "Launching the installer (administrator check)...",
    "Up.DownloadError": "Download failed: {0}",
    "Up.InstallError": "Could not launch the installer: {0}",
    "Btn.UpdateNow": "Update now",
    "Btn.Later": "Later",
    "Btn.Refuse": "Decline",

    // Port conflict (NEW: the desktop app has no such card)
    "Status.PortBusy": "Port {0} busy",
    "Port.UsedBy": "{0} (PID {1}) is using this port.",
    "Btn.KillAndStart": "Kill {0} and start",
    "Port.KillTitle": "Kill the application?",
    "Port.KillBody":
      "{0} (PID {1}) is using port {2}.\n\nKill it to free the port and start the server?\n\nAny unsaved data in that application will be lost.",
    "Port.KillFailed": "Port {0} is still busy.",
    // System tray context menu (native, built in Rust via set_tray_labels).
    "Tray.Show": "Show OpenDrop",
    "Tray.Quit": "Quit OpenDrop",
  },
} as const;

export type StringKey = keyof (typeof STRINGS)["fr"];

export type T = (key: StringKey, ...args: string[]) => string;

/** Lang.Format: {0}/{1} placeholders, like the desktop's string formatting. */
export function makeT(lang: Lang): T {
  const table = STRINGS[lang] as Record<string, string>;
  return (key, ...args) => {
    let s = table[key] ?? key;
    args.forEach((a, i) => {
      s = s.replaceAll(`{${i}}`, a);
    });
    return s;
  };
}

/** QuotaUsage.Format: Go/Mo/Ko/o (fr, comma) or GB/MB/KB/B (en, dot). */
export function formatBytes(bytes: number, lang: Lang): string {
  const fr = lang === "fr";
  const trim = (s: string) => s.replace(/(\.\d*?)0+$/, "$1").replace(/\.$/, "");
  let number: string;
  let unit: string;
  if (bytes >= 1024 ** 3) {
    number = trim((bytes / 1024 ** 3).toFixed(3));
    unit = fr ? "Go" : "GB";
  } else if (bytes >= 1024 ** 2) {
    number = trim((bytes / 1024 ** 2).toFixed(1));
    unit = fr ? "Mo" : "MB";
  } else if (bytes >= 1024) {
    number = trim((bytes / 1024).toFixed(1));
    unit = fr ? "Ko" : "KB";
  } else {
    number = String(bytes);
    unit = fr ? "o" : "B";
  }
  return fr ? `${number.replace(".", ",")} ${unit}` : `${number} ${unit}`;
}

/**
 * SettingsWindow's TryParseQuota: "0,5 go" / "500 mo" / "10.75" -> bytes.
 * A bare number is read as GB, 0 = unlimited. Returns null when invalid.
 */
export function parseQuota(text: string): number | null {
  const m = text
    .trim()
    .toLowerCase()
    .match(/^(\d+(?:[.,]\d+)?)\s*(go|mo|gb|mb)?$/);
  if (!m) return null;
  const value = Number(m[1].replace(",", "."));
  const unit = m[2] ?? "go";
  const factor = unit.startsWith("m") ? 1024 ** 2 : 1024 ** 3;
  return Math.round(value * factor);
}

/** Quota bytes -> the settings box text, so the value round-trips. */
export function formatQuotaInput(bytes: number): string {
  if (bytes === 0) return "0";
  if (bytes % 1024 ** 3 === 0) return `${bytes / 1024 ** 3} go`;
  return `${Math.round(bytes / 1024 ** 2)} mo`;
}
