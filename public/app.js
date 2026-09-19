(function () {
  var encoded = window.SITE_DATA_B64;
  var heroStats = document.getElementById('hero-stats');
  var genreFilters = document.getElementById('genre-filters');
  var albumGrid = document.getElementById('album-grid');
  var albumSectionTitle = document.getElementById('album-section-title');
  var albumSectionMeta = document.getElementById('album-section-meta');
  var sortControls = document.getElementById('sort-controls');

  var activeGenre = 'all';
  var sortMode = 'latest';
  var genres = [];
  var channels = [];
  var albums = [];
  var sortModes = [
    { id: 'latest', label: '\uCD5C\uC2E0\uC21C' },
    { id: 'oldest', label: '\uC624\uB798\uB41C\uC21C' },
    { id: 'category', label: '\uCE74\uD14C\uACE0\uB9AC' }
  ];

  function decodeBase64Utf8(value) {
    var binary = atob(value);
    var bytes = new Uint8Array(binary.length);
    for (var i = 0; i < binary.length; i += 1) {
      bytes[i] = binary.charCodeAt(i);
    }
    return new TextDecoder('utf-8').decode(bytes);
  }

  // 필터 버튼의 id 를 만든다.
  //
  // ⚠️ 한글을 지우면 안 된다. 예전엔 [^a-z0-9] 를 전부 '-' 로 바꿨는데, 그러면
  // 한글로만 된 채널명이 통째로 사라져 빈 문자열이 되고 전부 'misc' 로 떨어졌다.
  // 실제로 '굳이 송'과 '쉬어가는 감성 음악'이 같은 id 를 갖게 되어, 먼저 온 쪽만
  // 버튼이 생기고 나머지 21편이 그 버튼에 흡수됐다(감성 음악 버튼이 아예 안 보임).
  // \p{L}(문자)·\p{N}(숫자)을 유니코드 단위로 남겨 한글 채널명도 고유 id 를 갖게 한다.
  function slugifyGenre(value) {
    return (value || '')
      .toLowerCase()
      .trim()
      .replace(/&/g, ' and ')
      .replace(/[^\p{L}\p{N}]+/gu, '-')
      .replace(/^-+|-+$/g, '') || 'misc';
  }

  function formatGenreLabel(value) {
    var trimmed = (value || '').trim();
    if (!trimmed) {
      return 'Misc';
    }
    if (/^[a-z]+$/.test(trimmed)) {
      return trimmed.charAt(0).toUpperCase() + trimmed.slice(1);
    }
    return trimmed;
  }

  function getLocalCoverPath(index) {
    return 'assets/covers/album-' + String(index + 1).padStart(3, '0') + '.jpg';
  }

  function escapeHtml(value) {
    return String(value || '').replace(/[&<>"']/g, function (char) {
      return {
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#39;'
      }[char];
    });
  }

  function buildCatalog(rows) {
    var genreMap = new Map();
    var channelMap = new Map();
    var items = rows.map(function (row, index) {
      var rawGenre = row.genre || 'Misc';
      var genreId = slugifyGenre(rawGenre);
      var isChannel = row.source === 'youtube-api';

      if (isChannel) {
        if (!channelMap.has(genreId)) {
          channelMap.set(genreId, formatGenreLabel(rawGenre));
        }
      } else {
        if (!genreMap.has(genreId)) {
          genreMap.set(genreId, formatGenreLabel(rawGenre));
        }
      }

      return {
        genre: genreId,
        isChannel: isChannel,
        title: row.title,
        count: row.track_count || '',
        url: row.playlist_url,
        thumbnail: row.thumbnail_url || '',
        localThumbnail: row.local_cover || getLocalCoverPath(index),
        published: row.published_at || '',
        categoryLabel: formatGenreLabel(rawGenre),
        order: index
      };
    }).filter(function (item) {
      return item.title && item.url;
    });

    var genreItems = [{ id: 'all', label: '\uC804\uCCB4' }];
    genreMap.forEach(function (label, id) {
      genreItems.push({ id: id, label: label });
    });

    var channelItems = [];
    channelMap.forEach(function (label, id) {
      channelItems.push({ id: id, label: label });
    });

    return { genres: genreItems, channels: channelItems, albums: items };
  }

  function renderStats() {
    var trackTotal = albums.reduce(function (sum, album) {
      var count = parseInt(album.count, 10);
      return Number.isNaN(count) ? sum : sum + count;
    }, 0);

    var stats = [
      { value: String(albums.length), label: '\uB4F1\uB85D \uC568\uBC94' },
      { value: String(Math.max(genres.length - 1, 0)), label: '\uC7A5\uB974 \uD544\uD130' },
      { value: String(trackTotal), label: '\uD45C\uC2DC\uB41C \uC218\uB85D\uACE1 \uC218' },
      { value: 'LOCAL', label: '\uCEE4\uBC84 \uC6B0\uC120 \uAD6C\uC870' }
    ];

    heroStats.innerHTML = stats.map(function (item) {
      return '<div class="stat-card"><strong>' + item.value + '</strong><span>' + item.label + '</span></div>';
    }).join('');
  }

  function renderSortControls() {
    sortControls.innerHTML = sortModes.map(function (mode) {
      var activeClass = mode.id === sortMode ? ' is-active' : '';
      return '<button type="button" class="sort-chip' + activeClass + '" data-sort="' + mode.id + '">' + mode.label + '</button>';
    }).join('');

    Array.prototype.forEach.call(sortControls.querySelectorAll('button'), function (button) {
      button.addEventListener('click', function () {
        sortMode = button.getAttribute('data-sort');
        renderSortControls();
        renderAlbums();
      });
    });
  }

  function renderGenreFilters() {
    var genreChips = genres.map(function (genre) {
      var activeClass = genre.id === activeGenre ? ' is-active' : '';
      return '<button type="button" class="filter-chip' + activeClass + '" data-genre="' + genre.id + '">' + genre.label + '</button>';
    }).join('');

    var channelChips = channels.map(function (ch) {
      var activeClass = ch.id === activeGenre ? ' is-active' : '';
      return '<button type="button" class="filter-chip filter-chip--channel' + activeClass + '" data-genre="' + ch.id + '">' + ch.label + '</button>';
    }).join('');

    var channelSection = channels.length
      ? '<p class="filter-section-label">내 채널</p>' + channelChips
      : '';

    genreFilters.innerHTML =
      '<p class="filter-section-label">장르</p>' + genreChips + channelSection;

    Array.prototype.forEach.call(genreFilters.querySelectorAll('button'), function (button) {
      button.addEventListener('click', function () {
        activeGenre = button.getAttribute('data-genre');
        renderGenreFilters();
        renderAlbums();
      });
    });
  }

  function sortByPublished(list, newestFirst) {
    // 업로드 날짜 있는 YouTube 항목을 먼저 정렬한다. 날짜 없는 정적 앨범은 뒤에서 기존 순서를 유지한다.
    return list.slice().sort(function (a, b) {
      var aHasDate = Boolean(a.published);
      var bHasDate = Boolean(b.published);
      if (aHasDate && bHasDate) {
        return newestFirst
          ? b.published.localeCompare(a.published)
          : a.published.localeCompare(b.published);
      }
      if (aHasDate !== bHasDate) {
        return aHasDate ? -1 : 1;
      }
      return a.order - b.order;
    });
  }

  function getBaseAlbums() {
    if (activeGenre === 'all') {
      return albums.slice();
    }
    return albums.filter(function (album) {
      return album.genre === activeGenre;
    });
  }

  function getFilteredAlbums() {
    var filtered = getBaseAlbums();
    if (sortMode === 'oldest') {
      return sortByPublished(filtered, false);
    }
    if (sortMode === 'category') {
      return filtered.slice().sort(function (a, b) {
        var group = a.categoryLabel.localeCompare(b.categoryLabel, 'ko');
        if (group) {
          return group;
        }
        return sortByPublished([a, b], true)[0] === a ? -1 : 1;
      });
    }
    return sortByPublished(filtered, true);
  }

  function buildCoverTag(album) {
    var remote = album.thumbnail ? ' data-remote-src="' + escapeHtml(album.thumbnail) + '"' : '';
    return '<img src="' + escapeHtml(album.localThumbnail) + '" alt="' + escapeHtml(album.title) + ' \uC568\uBC94 \uCEE4\uBC84" loading="lazy" referrerpolicy="no-referrer"' + remote + ' onerror="var r=this.getAttribute(\'data-remote-src\'); if(r && this.src.indexOf(r)===-1){ this.src=r; this.removeAttribute(\'data-remote-src\'); } else { this.onerror=null; this.src=\'assets/cover-placeholder.svg\'; }">';
  }

  function renderAlbumCard(album) {
    return [
      '<a class="album-card" href="' + escapeHtml(album.url) + '" target="_blank" rel="noreferrer">',
      buildCoverTag(album),
      '<div class="album-card-body">',
      '<p class="album-count">' + escapeHtml(album.count) + '\uACE1</p>',
      '<h3>' + escapeHtml(album.title) + '</h3>',
      '<span class="album-card-link">' + (album.isChannel ? '\uC601\uC0C1 \uBCF4\uAE30' : '\uC7AC\uC0DD\uBAA9\uB85D \uC5F4\uAE30') + '</span>',
      '</div>',
      '</a>'
    ].join('');
  }

  function renderGroupedAlbums(filtered) {
    var groups = new Map();
    filtered.forEach(function (album) {
      if (!groups.has(album.genre)) {
        groups.set(album.genre, {
          label: album.categoryLabel,
          isChannel: album.isChannel,
          items: []
        });
      }
      groups.get(album.genre).items.push(album);
    });

    return Array.from(groups.values()).map(function (group) {
      return [
        '<section class="album-group">',
        '<div class="album-group-head">',
        '<h3>' + escapeHtml(group.label) + '</h3>',
        '<span>' + group.items.length + '\uAC1C</span>',
        '</div>',
        '<div class="album-group-grid">',
        group.items.map(renderAlbumCard).join(''),
        '</div>',
        '</section>'
      ].join('');
    }).join('');
  }

  function renderAlbums() {
    var filtered = getFilteredAlbums();
    var genre = genres.find(function (item) { return item.id === activeGenre; });
    var channel = channels.find(function (item) { return item.id === activeGenre; });

    albumSectionTitle.textContent = channel ? channel.label : (genre ? genre.label : '\uC804\uCCB4 \uC568\uBC94');
    albumSectionMeta.textContent = filtered.length + '\uAC1C \uC568\uBC94 \u00B7 ' + sortModes.find(function (mode) { return mode.id === sortMode; }).label;
    albumGrid.classList.toggle('is-grouped', sortMode === 'category');

    if (!filtered.length) {
      albumGrid.innerHTML = '<div class="album-empty">\uC774 \uC7A5\uB974\uC5D0\uB294 \uC544\uC9C1 \uD45C\uC2DC\uD560 \uC568\uBC94\uC774 \uC5C6\uC2B5\uB2C8\uB2E4.</div>';
      return;
    }

    albumGrid.innerHTML = sortMode === 'category'
      ? renderGroupedAlbums(filtered)
      : filtered.map(renderAlbumCard).join('');
  }

  if (!encoded) {
    heroStats.innerHTML = '<div class="stat-card"><strong>0</strong><span>\uB370\uC774\uD130 \uC5C6\uC74C</span></div>';
    albumGrid.innerHTML = '<div class="album-empty">data.js\uC5D0 \uC568\uBC94 \uB370\uC774\uD130\uAC00 \uC5C6\uC2B5\uB2C8\uB2E4.</div>';
    return;
  }

  var catalog = JSON.parse(decodeBase64Utf8(encoded));
  var parsed = buildCatalog(catalog);
  genres = parsed.genres;
  channels = parsed.channels;
  albums = parsed.albums;
  renderStats();
  renderGenreFilters();
  renderSortControls();
  renderAlbums();
}());
