(function () {
  var encoded = window.SITE_DATA_B64;
  var heroStats = document.getElementById('hero-stats');
  var genreFilters = document.getElementById('genre-filters');
  var albumGrid = document.getElementById('album-grid');
  var albumSectionTitle = document.getElementById('album-section-title');
  var albumSectionMeta = document.getElementById('album-section-meta');

  var activeGenre = 'all';
  var genres = [];
  var channels = [];
  var albums = [];

  function decodeBase64Utf8(value) {
    var binary = atob(value);
    var bytes = new Uint8Array(binary.length);
    for (var i = 0; i < binary.length; i += 1) {
      bytes[i] = binary.charCodeAt(i);
    }
    return new TextDecoder('utf-8').decode(bytes);
  }

  function slugifyGenre(value) {
    return (value || '')
      .toLowerCase()
      .trim()
      .replace(/&/g, ' and ')
      .replace(/[^a-z0-9]+/g, '-')
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
        published: row.published_at || ''
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

  function sortNewestFirst(list) {
    // 업로드 날짜 내림차순(최신이 위로). 날짜 없는 항목(정적 앨범)은 아래로.
    return list.slice().sort(function (a, b) {
      return (b.published || '').localeCompare(a.published || '');
    });
  }

  function getFilteredAlbums() {
    if (activeGenre === 'all') {
      return sortNewestFirst(albums);
    }
    var filtered = albums.filter(function (album) {
      return album.genre === activeGenre;
    });
    // 채널(YouTube 업로드) 보기는 최신이 위로(업로드 날짜 내림차순).
    // published 값이 없으면(아직 미수집) 수집 순서(최신순)를 유지한다.
    var isChannelView = channels.some(function (ch) { return ch.id === activeGenre; });
    if (isChannelView) {
      return sortNewestFirst(filtered);
    }
    return filtered.reverse();
  }

  function buildCoverTag(album) {
    var remote = album.thumbnail ? ' data-remote-src="' + album.thumbnail + '"' : '';
    return '<img src="' + album.localThumbnail + '" alt="' + album.title + ' \uC568\uBC94 \uCEE4\uBC84" loading="lazy" referrerpolicy="no-referrer"' + remote + ' onerror="var r=this.getAttribute(\'data-remote-src\'); if(r && this.src.indexOf(r)===-1){ this.src=r; this.removeAttribute(\'data-remote-src\'); } else { this.onerror=null; this.src=\'assets/cover-placeholder.svg\'; }">';
  }

  function renderAlbums() {
    var filtered = getFilteredAlbums();
    var genre = genres.find(function (item) { return item.id === activeGenre; });
    var channel = channels.find(function (item) { return item.id === activeGenre; });

    albumSectionTitle.textContent = channel ? channel.label : (genre ? genre.label : '\uC804\uCCB4 \uC568\uBC94');
    albumSectionMeta.textContent = filtered.length + '\uAC1C \uC568\uBC94';

    if (!filtered.length) {
      albumGrid.innerHTML = '<div class="album-empty">\uC774 \uC7A5\uB974\uC5D0\uB294 \uC544\uC9C1 \uD45C\uC2DC\uD560 \uC568\uBC94\uC774 \uC5C6\uC2B5\uB2C8\uB2E4.</div>';
      return;
    }

    albumGrid.innerHTML = filtered.map(function (album) {
      return [
        '<a class="album-card" href="' + album.url + '" target="_blank" rel="noreferrer">',
        buildCoverTag(album),
        '<div class="album-card-body">',
        '<p class="album-count">' + album.count + '\uACE1</p>',
        '<h3>' + album.title + '</h3>',
        '<span class="album-card-link">' + (album.isChannel ? '\uC601\uC0C1 \uBCF4\uAE30' : '\uC7AC\uC0DD\uBAA9\uB85D \uC5F4\uAE30') + '</span>',
        '</div>',
        '</a>'
      ].join('');
    }).join('');
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
  renderAlbums();
}());
