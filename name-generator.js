var players = [
    'Alan Shearer',
    'Wayne Rooney',
    'Andrew Cole',
    'Sergio Agüero',
    'Frank Lampard',
    'Thierry Henry',
    'Robbie Fowler',
    'Jermain Defoe',
    'Michael Owen',
    'Les Ferdinand',
    'Teddy Sheringham',
    'Robin van Persie',
    'Harry Kane',
    'Jimmy Floyd Hasselbaink',
    'Robbie Keane',
    'Nicolas Anelka',
    'Dwight Yorke',
    'Steven Gerrard',
    'Romelu Lukaku',
    'Ian Wright',
];

var adjectives = [
    'brawny',
    'wide-eyed',
    'ambiguous',
    'rainy',
    'cruel',
    'wiry',
    'beneficial',
    'ashamed',
    'tangy',
    'brainy',
    'tidy',
    'futuristic',
    'juvenile',
    'youthful',
    'plausible',
    'drunk',
    'powerful',
    'deafening',
    'funny',
    'aquatic',
    'jobless',
    'dry',
    'yielding',
    'subsequent',
    'dazzling',
    'second-hand',
    'tiny',
    'rhetorical',
    'witty',
    'deadpan',
    'mysterious',
    'lame',
    'long',
    'giddy',
    'faulty',
    'loutish',
    'alleged',
    'secret',
    'loud',
    'tiresome',
    'tense',
    'annoying',
    'piquant',
    'good',
    'pale',
    'white',
    'knotty',
    'sick',
    'ajar',
    'mute',
    'awake',
    'doubtful',
    'intelligent',
    'flowery',
    'wicked',
    'grumpy',
    'wistful',
    'cultured',
    'overconfident',
    'cooing',
    'sturdy',
    'obeisant',
    'nostalgic',
    'stale',
    'new',
    'elfin',
    'energetic',
    'scattered',
    'old-fashioned',
    'malicious',
    'painful',
    'damaged',
    'hellish',
    'wild',
    'raspy',
    'fabulous',
    'ossified',
    'afraid',
    'blushing',
    'useless',
    'aromatic',
    'hulking',
    'ablaze',
    'roasted',
    'ad hoc',
    'bumpy',
    'ill',
    'flat',
    'imaginary',
    'melted',
    'wiggly',
    'deserted',
    'shaggy',
    'dispensable',
    'responsible',
    'barbarous',
    'mere',
    'industrious',
    'whimsical',
    'teeny-tiny',
];

function getRandomInt(min, max) {
    min = Math.ceil(min);
    max = Math.floor(max);
    return Math.floor(Math.random() * (max - min + 1)) + min;
}

function capitalize(name) {
    return name.charAt(0).toUpperCase() + name.slice(1)
}

function randomName() {
    var player = players[getRandomInt(0, players.length)]
    var adj = adjectives[getRandomInt(0, adjectives.length)]
    return capitalize(adj) + ' ' + player
    
}